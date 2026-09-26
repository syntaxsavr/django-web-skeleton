"""Tests for the ops-file system (autonomous AI changes)."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from core import opsmanager
from core.models import OpsLog, SiteConfiguration


def base_doc():
    return {
        "meta": {
            "version": 1,
            "created_at": timezone.now().isoformat(),
            "author": "ai-agent:test",
            "purpose": "test ops file",
        },
        "operations": [{"type": "note", "text": "hello"}],
    }


@override_settings(OPS_SIGNING_KEY="test-key-123")
class OpsValidationTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_signature_roundtrip(self):
        doc = base_doc()
        doc["signature"] = opsmanager.sign_doc(doc)
        self.assertTrue(opsmanager.verify_signature(doc))
        doc["operations"][0]["text"] = "tampered"
        self.assertFalse(opsmanager.verify_signature(doc))

    def test_wrong_signature_rejected(self):
        doc = base_doc()
        doc["signature"] = "deadbeef"
        ok, status, reason = opsmanager.validate_doc(doc)
        self.assertTrue(ok)  # validation passes; signature check happens in process_pending
        self.assertFalse(opsmanager.verify_signature(doc))

    def test_expired_file_rejected(self):
        doc = base_doc()
        doc["meta"]["created_at"] = (timezone.now() - timedelta(hours=25)).isoformat()
        ok, status, _reason = opsmanager.validate_doc(doc)
        self.assertFalse(ok)
        self.assertEqual(status, OpsLog.Status.EXPIRED)

    def test_future_file_rejected(self):
        doc = base_doc()
        doc["meta"]["created_at"] = (timezone.now() + timedelta(hours=2)).isoformat()
        ok, status, _reason = opsmanager.validate_doc(doc)
        self.assertFalse(ok)
        self.assertEqual(status, OpsLog.Status.REJECTED)

    def test_sql_sandbox(self):
        cases = [
            ("CREATE TABLE IF NOT EXISTS ai_blog_post (id INTEGER PRIMARY KEY)", True),
            ("CREATE INDEX idx ON ai_blog_post (id)", True),
            ("ALTER TABLE ai_blog_post ADD COLUMN title TEXT", True),
            ("INSERT INTO ai_blog_post (title) VALUES ('hi')", True),
            ("UPDATE ai_blog_post SET title = 'x'", True),
            ("DELETE FROM ai_blog_post", True),
            ("DROP TABLE ai_blog_post", True),
            ("CREATE TABLE core_evil (id INTEGER)", False),
            ("DROP TABLE auth_user", False),
            ("UPDATE core_siteconfiguration SET site_name = 'x'", False),
            ("INSERT INTO auth_user (username) VALUES ('x')", False),
            ("PRAGMA journal_mode", False),
            ("SELECT * FROM sqlite_master", False),
            ("CREATE TABLE ai_a (id); DROP TABLE auth_user", False),
            ("SELECT * FROM ai_blog_post", False),
            ("", False),
        ]
        for sql, expected in cases:
            with self.subTest(sql=sql):
                ok, _reason = opsmanager.validate_sql(sql)
                self.assertEqual(ok, expected)

    def test_config_allowlist(self):
        doc = base_doc()
        doc["operations"] = [
            {"type": "config", "field": "announcement_text", "value": "Hello"},
            {"type": "config", "field": "enable_login_password", "value": False},
        ]
        ok, _status, reason = opsmanager.validate_doc(doc)
        self.assertFalse(ok)
        self.assertIn("not agent-editable", reason)


@override_settings(OPS_SIGNING_KEY="test-key-123")
class OpsExecutionTests(TestCase):
    def setUp(self):
        cache.clear()
        import tempfile

        self._tmp = tempfile.mkdtemp()
        self._ops_dir_patcher = patch.object(
            __import__("django.conf").conf.settings, "OPS_DIR", self._tmp
        )
        self._ops_dir_patcher.start()
        self.addCleanup(self._ops_dir_patcher.stop)

    def _write(self, doc, name="op-test.json"):
        from pathlib import Path

        path = Path(self._tmp) / "pending" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def test_apply_creates_and_populates_ai_table(self):
        doc = base_doc()
        doc["operations"] = [
            {"type": "sql", "sql": "CREATE TABLE IF NOT EXISTS ai_demo (id INTEGER PRIMARY KEY, title TEXT)"},
            {"type": "sql", "sql": "INSERT INTO ai_demo (title) VALUES ('first')"},
            {"type": "config", "field": "announcement_text", "value": "Built by ops"},
            {"type": "note", "text": "demo"},
        ]
        doc["signature"] = opsmanager.sign_doc(doc)
        self._write(doc)
        summary = opsmanager.process_pending()
        self.assertEqual(summary["applied"], 1)
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT title FROM ai_demo")
            self.assertEqual(cursor.fetchone()[0], "first")
        config = SiteConfiguration.get_solo()
        self.assertEqual(config.announcement_text, "Built by ops")
        self.assertEqual(OpsLog.objects.filter(status=OpsLog.Status.APPLIED).count(), 1)

    def test_failed_op_rolls_back_and_logs(self):
        doc = base_doc()
        doc["operations"] = [
            {"type": "sql", "sql": "CREATE TABLE IF NOT EXISTS ai_rollback (id INTEGER PRIMARY KEY)"},
            {"type": "sql", "sql": "INSERT INTO ai_nonexistent (x) VALUES (1)"},
        ]
        doc["signature"] = opsmanager.sign_doc(doc)
        self._write(doc)
        summary = opsmanager.process_pending()
        self.assertEqual(summary["failed"], 1)
        from django.db import connection

        with connection.cursor() as cursor:
            table = connection.introspection.table_names()
        self.assertNotIn("ai_rollback", table)  # atomic: nothing applied
        self.assertEqual(OpsLog.objects.filter(status=OpsLog.Status.FAILED).count(), 1)

    def test_expired_file_is_deleted_and_logged(self):
        doc = base_doc()
        doc["meta"]["created_at"] = (timezone.now() - timedelta(hours=30)).isoformat()
        doc["signature"] = opsmanager.sign_doc(doc)
        path = self._write(doc)
        summary = opsmanager.process_pending()
        self.assertEqual(summary["expired"], 1)
        self.assertFalse(path.exists())
        self.assertEqual(OpsLog.objects.filter(status=OpsLog.Status.EXPIRED).count(), 1)

    def test_unsigned_file_rejected(self):
        doc = base_doc()
        doc["signature"] = "nope"
        self._write(doc)
        summary = opsmanager.process_pending()
        self.assertEqual(summary["rejected"], 1)
        self.assertEqual(OpsLog.objects.filter(status=OpsLog.Status.REJECTED).count(), 1)
