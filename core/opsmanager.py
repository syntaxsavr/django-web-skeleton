"""The ops-file system: how an AI agent changes the site autonomously.

Protocol
========
An agent drops a signed JSON file into ``ops/pending/``::

    {
      "meta": {
        "version": 1,
        "created_at": "2026-09-27T10:00:00+00:00",
        "author": "ai-agent:<name>",
        "purpose": "build me a blog: create the ai_blog tables"
      },
      "operations": [
        {"type": "note",  "text": "Adds the blog schema."},
        {"type": "sql",   "sql": "CREATE TABLE IF NOT EXISTS ai_blog_post (...)"}
      ],
      "signature": "hex hmac-sha256 of the canonical JSON above without this key"
    }

Rules (enforced here, never trust the file):

- The signature must verify against OPS_SIGNING_KEY (or, in DEBUG only, a
  key derived from SECRET_KEY so vibecoding works out of the box).
- ``created_at`` is the validity anchor: files older than 24 hours (or
  from the future) are expired, deleted and logged. Stale pushes can
  never fire later.
- SQL may only CREATE/ALTER/INSERT/UPDATE/DELETE/DROP tables with the
  ``ai_`` prefix - core tables, auth tables and configuration are
  untouchable. PRAGMA/ATTACH/sqlite_master and multi-statement strings
  are rejected.
- ``config`` operations may only set allow-listed content fields.
  Authentication, consent, CSP, rate limits and every other security
  switch are the human's alone (see PROTECTED_CONFIG_FIELDS).
- Every processed file is logged to the OpsLog table, and the file itself
  is moved to ``ops/archive/`` or ``ops/failed/`` - the pending directory
  never keeps stale state.
"""

import hashlib
import hmac
import json
import logging
import re
import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from core.models import CONFIG_CACHE_KEY, OpsLog, SiteConfiguration

logger = logging.getLogger(__name__)

OPS_VERSION = 1
MAX_FILE_TTL = timedelta(hours=24)
MAX_CLOCK_SKEW = timedelta(minutes=5)
MAX_OPERATIONS = 50
AI_TABLE_PREFIX = "ai_"

# Tables an ops file may NEVER touch (the security fallback invariants).
PROTECTED_TABLE_PATTERN = re.compile(
    r"^(auth_|django_|accounts_|core_|otp_|admin_|sessions|social_)"
)

# SiteConfiguration fields an ops file may set: content only, never security.
SAFE_CONFIG_FIELDS = {
    "site_name": str,
    "default_meta_description": str,
    "footer_note": str,
    "footer_bottom_left": str,
    "footer_bottom_right": str,
    "announcement_text": str,
    "announcement_url": str,
    "navigation_menu_label": str,
    "theme_color": str,
}

SQL_FORBIDDEN_TOKENS = (
    "pragma",
    "attach",
    "detach",
    "vacuum",
    "reindex",
    "sqlite_master",
    "sqlite_sequence",
    "sqlite_temp",
)


def _signing_key() -> bytes | None:
    key = getattr(settings, "OPS_SIGNING_KEY", "")
    if key:
        return key.encode()
    if getattr(settings, "DEBUG", False):
        # Dev convenience: derive from the secret so vibecoding needs no
        # extra configuration. Production must set OPS_SIGNING_KEY.
        return hashlib.sha256(("ops+" + settings.SECRET_KEY).encode()).hexdigest().encode()
    return None


def canonical_bytes(doc: dict) -> bytes:
    unsigned = {k: v for k, v in doc.items() if k != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_doc(doc: dict, key: bytes | None = None) -> str:
    key = key or _signing_key()
    if key is None:
        raise RuntimeError("OPS_SIGNING_KEY is not configured.")
    return hmac.new(key, canonical_bytes(doc), hashlib.sha256).hexdigest()


def verify_signature(doc: dict) -> bool:
    key = _signing_key()
    signature = doc.get("signature", "")
    if not key or not isinstance(signature, str):
        return False
    return hmac.compare_digest(signature, sign_doc(doc, key))


def _table_from_sql(sql: str, pattern: re.Pattern, group: int) -> str | None:
    match = pattern.search(sql)
    return match.group(group).strip("`\"'[]; ") if match else None


SQL_PATTERNS = (
    (re.compile(r"^CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][\w]*)", re.I), 2),
    (re.compile(r"^CREATE\s+(UNIQUE\s+)?INDEX\s+(IF\s+NOT\s+EXISTS\s+)?\S+\s+ON\s+([a-zA-Z_][\w]*)", re.I), 3),
    (re.compile(r"^ALTER\s+TABLE\s+([a-zA-Z_][\w]*)", re.I), 1),
    (re.compile(r"^INSERT\s+OR\s+\w+\s+INTO\s+([a-zA-Z_][\w]*)", re.I), 1),
    (re.compile(r"^INSERT\s+INTO\s+([a-zA-Z_][\w]*)", re.I), 1),
    (re.compile(r"^UPDATE\s+([a-zA-Z_][\w]*)", re.I), 1),
    (re.compile(r"^DELETE\s+FROM\s+([a-zA-Z_][\w]*)", re.I), 1),
    (re.compile(r"^DROP\s+TABLE\s+(IF\s+EXISTS\s+)?([a-zA-Z_][\w]*)", re.I), 2),
)

# Every table a statement READS from (FROM x / JOIN x) - the write target
# alone is not enough: INSERT INTO ai_x SELECT * FROM auth_user would copy
# protected data into the agent-readable sandbox.
SQL_READ_PATTERN = re.compile(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][\w]*)", re.I)
# ALTER TABLE x RENAME TO y - the new name must stay inside the sandbox.
SQL_RENAME_PATTERN = re.compile(r"\bRENAME\s+TO\s+([a-zA-Z_][\w]*)", re.I)


def validate_sql(sql: str) -> tuple[bool, str]:
    """Validate one SQL statement against the ai_ sandbox.

    Two independent checks: (1) every table the statement writes to, reads
    from or renames to must carry the ai_ prefix (and never match the
    protected prefixes), and (2) only allow-listed statement types. A
    signed file can therefore copy content between its own tables but can
    never read protected data out of them."""
    statement = sql.strip().rstrip(";").strip()
    lowered = statement.lower()
    if not statement:
        return False, "empty statement"
    if any(token in lowered for token in SQL_FORBIDDEN_TOKENS):
        return False, "forbidden token (pragma/attach/system tables)"
    if ";" in statement:
        return False, "multiple statements are not allowed"

    def _table_ok(name: str) -> str | None:
        if PROTECTED_TABLE_PATTERN.match(name):
            return f"table '{name}' is protected and out of reach for ops files"
        if not name.startswith(AI_TABLE_PREFIX):
            return f"table '{name}' is outside the ai_ sandbox; AI-created tables must start with {AI_TABLE_PREFIX}"
        return None

    rename = SQL_RENAME_PATTERN.search(statement)
    if rename:
        problem = _table_ok(rename.group(1))
        if problem:
            return False, "rename: " + problem
    for match in SQL_READ_PATTERN.finditer(statement):
        problem = _table_ok(match.group(1))
        if problem:
            return False, "read: " + problem

    for pattern, group in SQL_PATTERNS:
        match = pattern.match(statement)
        if match:
            target = match.group(group).strip("`\"'[] ")
            if not target:
                return False, "could not determine the target table"
            problem = _table_ok(target)
            if problem:
                return False, problem
            return True, ""
    return False, "statement type not allowed (use CREATE/ALTER/INSERT/UPDATE/DELETE/DROP on ai_ tables)"


def validate_operations(operations) -> tuple[bool, str]:
    if not isinstance(operations, list) or not operations:
        return False, "operations must be a non-empty list"
    if len(operations) > MAX_OPERATIONS:
        return False, f"too many operations (max {MAX_OPERATIONS})"
    for index, op in enumerate(operations):
        if not isinstance(op, dict) or "type" not in op:
            return False, f"operation {index}: missing type"
        kind = op.get("type")
        if kind == "sql":
            ok, reason = validate_sql(op.get("sql", ""))
            if not ok:
                return False, f"operation {index} (sql): {reason}"
        elif kind == "config":
            field = op.get("field", "")
            if field not in SAFE_CONFIG_FIELDS:
                return False, f"operation {index} (config): field '{field}' is not agent-editable"
            if not isinstance(op.get("value"), SAFE_CONFIG_FIELDS[field]):
                return False, f"operation {index} (config): wrong value type for '{field}'"
            value = op["value"]
            if isinstance(value, str) and len(value) > 300:
                return False, f"operation {index} (config): value too long for '{field}'"
        elif kind == "note":
            if not isinstance(op.get("text"), str) or len(op["text"]) > 500:
                return False, f"operation {index} (note): text missing or too long"
        else:
            return False, f"operation {index}: unknown type '{kind}'"
    return True, ""


def validate_doc(doc: dict) -> tuple[bool, str, str]:
    """Full validation. Returns (ok, status, reason)."""
    meta = doc.get("meta")
    if not isinstance(meta, dict) or meta.get("version") != OPS_VERSION:
        return False, OpsLog.Status.REJECTED, "unsupported meta.version"
    created_at = meta.get("created_at")
    try:
        created = timezone.datetime.fromisoformat(created_at)
        if timezone.is_naive(created):
            created = timezone.make_aware(created)
    except (ValueError, TypeError):
        return False, OpsLog.Status.REJECTED, "meta.created_at is not an ISO timestamp"
    now = timezone.now()
    if created > now + MAX_CLOCK_SKEW:
        return False, OpsLog.Status.REJECTED, "created_at is in the future"
    if now - created > MAX_FILE_TTL:
        return False, OpsLog.Status.EXPIRED, "older than 24 hours - stale pushes never fire"
    ok, reason = validate_operations(doc.get("operations"))
    if not ok:
        return False, OpsLog.Status.REJECTED, reason
    return True, "", ""


def _pending_dir() -> Path:
    return Path(settings.OPS_DIR) / "pending"


def _move_to(file_path: Path, subdirectory: str) -> None:
    target_dir = Path(settings.OPS_DIR) / subdirectory
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / file_path.name
    counter = 1
    while target.exists():
        target = target_dir / f"{file_path.stem}-{counter}{file_path.suffix}"
        counter += 1
    shutil.move(str(file_path), str(target))


def process_pending(apply: bool = True) -> dict:
    """Validate and apply every pending ops file. Returns a summary."""
    summary = {"applied": 0, "failed": 0, "expired": 0, "rejected": 0, "skipped": 0}
    if _signing_key() is None:
        # no signing key configured in production: leave files untouched
        summary["skipped"] = 1
        logger.warning("Ops: OPS_SIGNING_KEY is not configured; pending files are left alone.")
        return summary

    pending = sorted(_pending_dir().glob("*.json"))
    for file_path in pending:
        try:
            doc = json.loads(file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _record_and_move(file_path, None, OpsLog.Status.FAILED, f"unreadable JSON: {exc}")
            summary["failed"] += 1
            continue

        if not verify_signature(doc):
            _record_and_move(file_path, doc, OpsLog.Status.REJECTED, "signature does not verify")
            summary["rejected"] += 1
            continue

        ok, status, reason = validate_doc(doc)
        if not ok:
            _record_and_move(file_path, doc, status, reason)
            summary["failed" if status == OpsLog.Status.FAILED else "expired" if status == OpsLog.Status.EXPIRED else "rejected"] += 1
            continue

        if not apply:
            summary["skipped"] += 1
            continue

        try:
            with transaction.atomic():
                results = _execute(doc["operations"])
            _record_and_move(file_path, doc, OpsLog.Status.APPLIED, json.dumps(results, ensure_ascii=False))
            summary["applied"] += 1
        except Exception as exc:  # rolled back atomically
            _record_and_move(file_path, doc, OpsLog.Status.FAILED, f"{type(exc).__name__}: {exc}")
            summary["failed"] += 1
    return summary


def _execute(operations) -> list[dict]:
    """Execute validated operations inside the caller's transaction."""
    from django.db import connection

    results = []
    config_touched = False
    config = SiteConfiguration.get_solo()
    for op in operations:
        kind = op["type"]
        if kind == "sql":
            with connection.cursor() as cursor:
                cursor.execute(op["sql"].strip().rstrip(";"))
                results.append({"type": "sql", "detail": op.get("description", op["sql"][:120]), "rows": cursor.rowcount})
        elif kind == "config":
            setattr(config, op["field"], op["value"])
            config_touched = True
            results.append({"type": "config", "field": op["field"]})
        elif kind == "note":
            results.append({"type": "note", "text": op["text"]})
    if config_touched:
        config.full_clean()
        config.save()
        cache.delete(CONFIG_CACHE_KEY)
    return results


def _record_and_move(file_path: Path, doc: dict | None, status, detail: str) -> None:
    meta = (doc or {}).get("meta", {})
    destination = {
        OpsLog.Status.APPLIED: "archive",
        OpsLog.Status.FAILED: "failed",
        OpsLog.Status.EXPIRED: "expired",
        OpsLog.Status.REJECTED: "failed",
    }.get(status, "failed")
    _move_to(file_path, destination)
    OpsLog.objects.create(
        file_name=file_path.name,
        status=status,
        author=str(meta.get("author", ""))[:120],
        purpose=str(meta.get("purpose", ""))[:300],
        created_at=meta.get("created_at"),
        detail=detail[:4000],
    )
    logger.info("Ops %s: %s (%s)", status, file_path.name, detail[:200])
