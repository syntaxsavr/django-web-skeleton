"""Tests for the accounts app: auth methods, privacy flows, retention."""

import hashlib
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import (
    ConsentText,
    DataExportRequest,
    LoginEvent,
    RegistrationField,
    UserProfile,
)
from core.models import SiteConfiguration

User = get_user_model()


def fresh_config(**kwargs):
    from core.models import SiteConfiguration as C

    config = C.get_solo()
    for key, value in kwargs.items():
        setattr(config, key, value)
    config.save()
    return config


class IsolatedTest(TestCase):
    def setUp(self):
        cache.clear()


class PasswordLoginTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("maria", "maria@example.com", "S3cure!pass")
        self.profile = UserProfile.objects.create(user=self.user)

    def test_username_and_email_login(self):
        fresh_config(login_identifier_mode="either")
        for identifier in ("maria", "maria@example.com"):
            response = self.client.post("/accounts/login/", {"identifier": identifier, "password": "S3cure!pass"})
            self.assertEqual(response.status_code, 302, identifier)
            self.client.logout()

    def test_login_records_event(self):
        fresh_config(login_identifier_mode="username")
        self.client.post("/accounts/login/", {"identifier": "maria", "password": "S3cure!pass"})
        event = LoginEvent.objects.get(user=self.user)
        self.assertEqual(event.method, "password")
        self.assertEqual(event.ip_address, "127.0.0.1")

    def test_suspended_account_cannot_login(self):
        self.profile.data_deletion_at = timezone.now() + timedelta(hours=10)
        self.profile.save()
        response = self.client.post(
            "/accounts/login/", {"identifier": "maria", "password": "S3cure!pass"}, follow=True
        )
        self.assertContains(response, "suspended")

    def test_identifier_mode_email_rejects_username(self):
        fresh_config(login_identifier_mode="email")
        response = self.client.post("/accounts/login/", {"identifier": "maria", "password": "S3cure!pass"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LoginEvent.objects.exists())


class EmailCodeLoginTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        fresh_config(enable_login_email_otp=True, enable_login_password=False)
        self.user = User.objects.create_user("codie", "codie@example.com", None)
        self.user.set_unusable_password()
        self.user.save()
        UserProfile.objects.create(user=self.user)

    def test_response_hides_account_existence(self):
        ghost = self.client.post("/accounts/login/code/", {"email": "ghost@example.com"}, follow=True)
        existing = self.client.post("/accounts/login/code/", {"email": "codie@example.com"}, follow=True)
        body_existing = existing.content.decode()
        body_ghost = ghost.content.decode()
        # identical, deliberately vague wording on both paths (mask the
        # typed address and the per-request CSRF token before comparing)
        self.assertIn("We may have sent a code", body_existing)
        self.assertIn("We may have sent a code", body_ghost)

        import re

        def mask(html, email):
            html = html.replace(email, "MASKED@x")
            return re.sub(r'name="csrfmiddlewaretoken" value="[^"]*"', "name=csrf", html)

        self.assertEqual(mask(body_existing, "codie@example.com"), mask(body_ghost, "ghost@example.com"))
        # the ghost address never receives anything
        self.assertFalse(any("ghost@example.com" in m.to for m in mail.outbox))

    def test_code_login_works(self):
        self.client.post("/accounts/login/code/", {"email": "codie@example.com"})
        code = mail.outbox[-1].body.split("code is ")[1].split("\n")[0].strip()
        response = self.client.post("/accounts/login/code/verify/", {"code": code})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(LoginEvent.objects.filter(user=self.user, method="email_otp").exists())

    def test_wrong_code_does_not_login(self):
        self.client.post("/accounts/login/code/", {"email": "codie@example.com"})
        response = self.client.post("/accounts/login/code/verify/", {"code": "000000"}, follow=True)
        self.assertContains(response, "wrong or expired")


class MagicLinkTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        fresh_config(enable_login_magic_link=True, enable_login_password=False)
        self.user = User.objects.create_user("maja", "maja@example.com", None)
        self.user.set_unusable_password()
        self.user.save()
        UserProfile.objects.create(user=self.user)

    def test_magic_link_login(self):
        self.client.post("/accounts/login/magic/", {"email": "maja@example.com"})
        match = re.search(r"/accounts/login/magic/([^/]+)/", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        response = self.client.get(f"/accounts/login/magic/{match.group(1)}/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(LoginEvent.objects.filter(user=self.user, method="magic").exists())
        self.client.logout()

    def test_reused_link_fails(self):
        self.client.post("/accounts/login/magic/", {"email": "maja@example.com"})
        token = re.search(r"/accounts/login/magic/([^/]+)/", mail.outbox[-1].body).group(1)
        self.client.get(f"/accounts/login/magic/{token}/")
        self.client.logout()
        response = self.client.get(f"/accounts/login/magic/{token}/", follow=True)
        self.assertContains(response, "invalid, used up or expired")


class AnonymousAccessTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        fresh_config(enable_login_anonymous=True, enable_login_password=False)

    def test_generate_and_login(self):
        response = self.client.post("/accounts/login/token/new/")
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(profile__is_anonymous=True)
        self.assertTrue(user.username)
        self.assertFalse(user.has_usable_password())
        token = self.client.session.get("show_new_token") or user.username
        self.client.logout()
        response = self.client.post("/accounts/login/token/", {"token": user.username})
        self.assertEqual(response.status_code, 302)

    def test_no_email_on_anonymous_accounts(self):
        self.client.post("/accounts/login/token/new/")
        user = User.objects.get(profile__is_anonymous=True)
        self.assertEqual(user.email, "")


class RegistrationConsentTests(IsolatedTest):
    def test_consents_captured_with_snapshot(self):
        fresh_config()
        ConsentText.objects.create(
            title="Privacy policy", slug="privacy", body="We store the minimum.",
            url="/privacy/", required=True, version=2,
        )
        payload = {
            "username": "consenty",
            "email": "consenty@example.com",
            "password1": "correct-horse-battery-99",
            "password2": "correct-horse-battery-99",
            "consent_privacy": "on",
        }
        response = self.client.post("/accounts/register/", payload)
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="consenty")
        consent = user.consents.get(slug="privacy")
        self.assertEqual(consent.version, 2)
        self.assertEqual(consent.title, "Privacy policy")

    def test_required_consent_blocks_registration(self):
        fresh_config()
        ConsentText.objects.create(title="Terms", slug="terms", body="Obey.", required=True)
        payload = {
            "username": "refusenik",
            "email": "refuse@example.com",
            "password1": "correct-horse-battery-99",
            "password2": "correct-horse-battery-99",
        }
        response = self.client.post("/accounts/register/", payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="refusenik").exists())

    def test_dynamic_field_stored_sanitized(self):
        fresh_config()
        RegistrationField.objects.create(label="City", slug="city", kind="text", required=True)
        payload = {
            "username": "urban",
            "email": "urban@example.com",
            "password1": "correct-horse-battery-99",
            "password2": "correct-horse-battery-99",
            "field_city": "<b>Berlin</b>",
        }
        response = self.client.post("/accounts/register/", payload)
        self.assertEqual(response.status_code, 302)
        profile = UserProfile.objects.get(user__username="urban")
        self.assertEqual(profile.extra_data["city"], "Berlin")

    def test_forced_completion_for_old_accounts(self):
        fresh_config()
        RegistrationField.objects.create(label="City", slug="city", kind="text", required=True)
        user = User.objects.create_user("legacy", "legacy@example.com", "S3cure!pass")
        UserProfile.objects.create(user=user)
        self.client.login(username="legacy", password="S3cure!pass")
        response = self.client.get("/account/", follow=True)
        self.assertEqual(response.request["PATH_INFO"], "/account/complete/")
        response = self.client.post("/account/complete/", {"field_city": "Vienna"})
        self.assertEqual(response.status_code, 302)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.extra_data["city"], "Vienna")


class DataExportTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("exporter", "exporter@example.com", "S3cure!pass")
        UserProfile.objects.create(user=self.user)
        self.client.login(username="exporter", password="S3cure!pass")
        self.config = fresh_config(export_wait_minutes=30, export_cooldown_days=28, export_retention_days=30)

    def test_request_then_wait_then_ready_then_download(self):
        import gzip

        from accounts import maintenance

        response = self.client.post("/account/privacy/export/")
        self.assertEqual(response.status_code, 302)
        entry = DataExportRequest.objects.get()
        self.assertEqual(entry.status, DataExportRequest.STATUS_WAITING)
        # waiting period: no download yet
        self.assertEqual(self.client.get(f"/account/privacy/export/{entry.pk}/download/").status_code, 404)
        # waiting period passes -> throttled processing builds the archive
        DataExportRequest.objects.filter(pk=entry.pk).update(ready_at=timezone.now())
        built = maintenance.process_due_exports()
        self.assertEqual(built, 1)
        entry.refresh_from_db()
        self.assertEqual(entry.status, DataExportRequest.STATUS_READY)
        response = self.client.get(f"/account/privacy/export/{entry.pk}/download/")
        self.assertEqual(response.status_code, 200)
        payload = gzip.decompress(entry.file.read())
        self.assertIn(b"exporter@example.com", payload)

    def test_cooldown_blocks_second_request(self):
        self.client.post("/account/privacy/export/")
        response = self.client.post("/account/privacy/export/", follow=True)
        self.assertContains(response, "request your next")
        self.assertEqual(DataExportRequest.objects.count(), 1)

    def test_throttled_processing_builds_one_per_pass(self):
        now = timezone.now()
        for _ in range(3):
            DataExportRequest.objects.create(
                user=self.user, ready_at=now, expires_at=now + timedelta(days=1)
            )
        from accounts import maintenance

        built = maintenance.process_due_exports()
        self.assertEqual(built, 1)

    def test_expired_archive_purged(self):
        from accounts import maintenance

        entry = DataExportRequest.objects.create(
            user=self.user,
            status=DataExportRequest.STATUS_READY,
            ready_at=timezone.now(),
            expires_at=timezone.now(),
        )
        DataExportRequest.objects.filter(pk=entry.pk).update(
            created=timezone.now() - timedelta(days=40)
        )
        maintenance.purge_expired_exports()
        entry.refresh_from_db()
        self.assertEqual(entry.status, DataExportRequest.STATUS_PURGED)


def gzip_decompress(content):
    import gzip

    return gzip.decompress(content)


class DataDeletionTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        fresh_config(deletion_delay_hours=72)
        self.user = User.objects.create_user("eraser", "eraser@example.com", "S3cure!pass")
        self.profile = UserProfile.objects.create(user=self.user, extra_data={"city": "X"})
        LoginEvent.objects.create(user=self.user, method="password")
        self.client.login(username="eraser", password="S3cure!pass")

    def _pass_code_step(self, purpose):
        self.client.post(f"/account/privacy/delete-{'data' if purpose == 'data_deletion' else 'account'}/", {"action": "request_code"})
        code = mail.outbox[-1].body.split("code is ")[1].split("\n")[0].strip()
        response = self.client.post(
            f"/account/privacy/delete-{'data' if purpose == 'data_deletion' else 'account'}/",
            {"action": "verify_code", "code": code},
        )
        return response

    def _pass_phrase_step(self, path):
        self.client.get(path)  # renders step 2 and generates the phrase
        key = "phrase_data_deletion" if "delete-data" in path else "phrase_account_deletion"
        phrase = self.client.session[key]
        return self.client.post(path, {"action": "confirm_phrase", "phrase": phrase})

    def test_data_deletion_schedules_and_suspends(self):
        from accounts import maintenance

        path = "/account/privacy/delete-data/"
        self._pass_code_step("data_deletion")
        response = self._pass_phrase_step(path)
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.data_deletion_at)
        self.assertFalse(User.objects.get(username="eraser").is_active)
        # executes only after the delay
        result = maintenance.execute_due_deletions()
        self.assertEqual(result["data"], 0)
        UserProfile.objects.filter(pk=self.profile.pk).update(
            data_deletion_at=timezone.now() - timedelta(minutes=1)
        )
        result = maintenance.execute_due_deletions()
        self.assertEqual(result["data"], 1)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.extra_data, {})
        self.assertTrue(User.objects.get(username="eraser").is_active)
        # technical trace kept (retention has not passed)
        self.assertTrue(LoginEvent.objects.filter(user=self.user).exists())

    def test_account_deletion_pseudonymises(self):
        from accounts import maintenance

        path = "/account/privacy/delete-account/"
        self._pass_code_step("account_deletion")
        self.client.get(path)  # renders step 2 and generates the phrase
        phrase = self.client.session["phrase_account_deletion"]
        response = self.client.post(path, {"action": "confirm_phrase", "phrase": phrase})
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.account_deletion_at)
        UserProfile.objects.filter(pk=self.profile.pk).update(
            account_deletion_at=timezone.now() - timedelta(minutes=1)
        )
        maintenance.execute_due_deletions()
        user = User.objects.get(pk=self.user.pk)
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.email, "")
        self.assertFalse(LoginEvent.objects.filter(user=user).exists())
        self.assertTrue(user.username.startswith("removed-"))


class MailhashedTests(IsolatedTest):
    def test_conversion_is_one_way(self):
        user = User.objects.create_user("hashme", "hashme@example.com", "S3cure!pass")
        UserProfile.objects.create(user=user)
        profile = UserProfile.objects.get(user=user)
        self.assertFalse(profile.mailhashed)
        profile.mailhashed = True
        profile.email_hash = hashlib.sha256(b"hashme@example.com").hexdigest()
        user.email = "hashed-invalid@invalid"
        user.save()
        profile.save()
        profile.refresh_from_db()
        self.assertTrue(profile.mailhashed)
        with self.assertRaises(Exception):
            profile.mailhashed = False
            profile.email_hash = "x"
            profile.full_clean()


class AuthMasterSwitchTests(IsolatedTest):
    def test_accounts_off_hides_routes_and_nav(self):
        fresh_config(enable_accounts=False)
        self.assertEqual(self.client.get("/accounts/login/").status_code, 404)
        self.assertEqual(self.client.get("/account/").status_code, 404)
        home = self.client.get("/").content.decode()
        self.assertNotIn("Sign in", home)

    def test_accounts_on_shows_login(self):
        fresh_config(enable_accounts=True)
        self.assertEqual(self.client.get("/accounts/login/").status_code, 200)


class Forced2faUsersTests(IsolatedTest):
    def test_user_forced_to_enroll(self):
        fresh_config(force_2fa_users=True)
        user = User.objects.create_user("forced", "forced@example.com", "S3cure!pass")
        UserProfile.objects.create(user=user)
        self.client.login(username="forced", password="S3cure!pass")
        response = self.client.get("/account/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("two-factor", response["Location"])

    def test_verified_user_passes(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice
        from django_otp.oath import TOTP
        import time

        fresh_config(force_2fa_users=True)
        user = User.objects.create_user("verified", "verified@example.com", "S3cure!pass")
        UserProfile.objects.create(user=user)
        device = TOTPDevice.objects.create(user=user, name="A", confirmed=True)
        self.client.login(username="verified", password="S3cure!pass")
        generator = TOTP(device.bin_key)
        generator.time = time.time()
        self.client.post("/account/two-factor/verify/", {"token": generator.token()})
        self.assertEqual(self.client.get("/account/").status_code, 200)


class SanitizationTests(IsolatedTest):
    def test_contact_message_stripped(self):
        from core.models import ContactMessage

        from core.sanitizers import clean_multiline, clean_text

        self.assertEqual(clean_text("<b onclick='x'>Hi</b>"), "Hi")
        # tags are stripped; their text content stays behind as inert text
        self.assertEqual(clean_multiline("line1\n<script>bad()</script>\nline2"), "line1\nbad()\nline2")

    def test_registration_value_stripped(self):
        fresh_config()
        RegistrationField.objects.create(label="Bio", slug="bio", kind="textarea")
        payload = {
            "username": "sri",
            "email": "sri@example.com",
            "password1": "correct-horse-battery-99",
            "password2": "correct-horse-battery-99",
            "field_bio": "<script>alert(1)</script>Clean text",
        }
        self.client.post("/accounts/register/", payload)
        profile = UserProfile.objects.get(user__username="sri")
        self.assertEqual(profile.extra_data["bio"], "alert(1)Clean text")
        self.assertNotIn("<", profile.extra_data["bio"])
