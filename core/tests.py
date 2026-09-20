"""Smoke tests: every mechanism in the skeleton has at least one assertion
that proves its control-panel switch actually changes behavior."""

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.test import TestCase, override_settings

from core.models import CONFIG_CACHE_KEY, ContactMessage, ProtectedPage, SiteConfiguration
from core.views import FORM_TS_SALT

User = get_user_model()


class ConfigIsolatedTestCase(TestCase):
    """Base class that clears the config cache between tests.

    SiteConfiguration.get_solo() caches in locmem, which transactions do
    not roll back; without this, a switch flipped in one test leaks into
    the next. It also resets django-ratelimit counters.
    """

    def setUp(self):
        cache.clear()
        SiteConfiguration.get_solo()


def fresh_config(**kwargs):
    config = SiteConfiguration.get_solo()
    for key, value in kwargs.items():
        setattr(config, key, value)
    config.save()
    return config


class PageSmokeTests(TestCase):
    def test_public_pages_render(self):
        for url in ["/", "/demo/", "/contact/"]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, url)

    def test_legal_pages_render_for_real_browsers(self):
        # The scraper block middleware 403s empty user agents; legal pages
        # are its protected zone, so tests must identify as a browser.
        for url in ["/privacy/", "/imprint/", "/accessibility/"]:
            with self.subTest(url=url):
                response = self.client.get(url, HTTP_USER_AGENT="Mozilla/5.0")
                self.assertEqual(response.status_code, 200, url)

    def test_machine_routes(self):
        cases = {
            "/robots.txt": "Sitemap:",
            "/llms.txt": "# Skeleton",
            "/llms-full.txt": "## Home",
            "/security.txt": "Contact:",
            "/.well-known/security.txt": "Contact:",
            "/humans.txt": "django-web-skeleton",
            "/sitemap.xml": "urlset",
        }
        for url, needle in cases.items():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn(needle, response.content.decode())

    def test_lazy_section_route_resolves_fragment(self):
        response = self.client.get("/lazy-section/demo-lazy-panel/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("You scrolled, we fetched", response.content.decode())

    def test_lazy_section_rejects_unknown_fragment(self):
        response = self.client.get("/lazy-section/does-not-exist/")
        self.assertEqual(response.status_code, 404)

    def test_error_pages(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Nothing at this address", response.content.decode())


class ConsentAndTrackingTests(ConfigIsolatedTestCase):
    def test_consent_assets_present_when_enabled(self):
        html = self.client.get("/").content.decode()
        self.assertIn("klaro-config.js", html)
        self.assertIn("skeleton-tracking-config", html)

    def test_consent_assets_absent_when_disabled(self):
        fresh_config(enable_cookie_consent=False)
        html = self.client.get("/").content.decode()
        self.assertNotIn("klaro-config.js", html)

    def test_tracker_ids_not_exposed_when_tracking_off(self):
        config = fresh_config(enable_tracking=False, google_analytics_measurement_id="G-XXXX")
        payload = config.tracking_data()
        self.assertEqual(payload["ids"], {})

    def test_tracker_ids_exposed_when_tracking_on(self):
        config = fresh_config(enable_tracking=True, google_analytics_measurement_id="G-TEST123")
        payload = config.tracking_data()
        self.assertEqual(payload["ids"]["googleAnalyticsId"], "G-TEST123")
        fresh_config(enable_tracking=False)


class SeoSwitchTests(ConfigIsolatedTestCase):
    def test_sitemap_respects_switch(self):
        self.assertIn("<loc>", self.client.get("/sitemap.xml").content.decode())
        fresh_config(enable_sitemap=False)
        content = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("<loc>", content)
        fresh_config(enable_sitemap=True)

    def test_llms_txt_respects_switch(self):
        fresh_config(enable_llms_txt=False)
        self.assertEqual(self.client.get("/llms.txt").status_code, 404)
        fresh_config(enable_llms_txt=True)

    def test_noindex_kill_switch(self):
        fresh_config(robots_noindex_whole_site=True)
        response = self.client.get("/")
        self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, nofollow")
        fresh_config(robots_noindex_whole_site=False)

    def test_account_pages_carry_noindex_header(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, nofollow")

    def test_indexnow_key_route_only_matches_configured_key(self):
        fresh_config(enable_indexnow=True, indexnow_key="testkey123456789")
        self.assertEqual(self.client.get("/testkey123456789.txt").status_code, 200)
        self.assertEqual(self.client.get("/wrongkey12345678.txt").status_code, 404)
        fresh_config(enable_indexnow=False, indexnow_key="")

    def test_jsonld_present(self):
        html = self.client.get("/demo/").content.decode()
        self.assertIn("application/ld+json", html)
        self.assertIn("BreadcrumbList", html)


class CspMiddlewareTests(ConfigIsolatedTestCase):
    def test_csp_header_on_public_pages(self):
        response = self.client.get("/")
        self.assertIn("Content-Security-Policy", response.headers)

    def test_csp_extends_with_matomo(self):
        fresh_config(enable_tracking=True, matomo_url="https://analytics.example.com")
        policy = self.client.get("/")["Content-Security-Policy"]
        self.assertIn("analytics.example.com", policy)
        fresh_config(enable_tracking=False, matomo_url="")

    def test_csp_switch_disables_header(self):
        fresh_config(enable_csp=False)
        response = self.client.get("/")
        self.assertNotIn("Content-Security-Policy", response.headers)
        fresh_config(enable_csp=True)


class ScraperBlockTests(ConfigIsolatedTestCase):
    def test_scraper_user_agent_is_blocked_on_legal_pages(self):
        response = self.client.get("/privacy/", HTTP_USER_AGENT="curl/8.0")
        self.assertEqual(response.status_code, 403)

    def test_normal_user_agent_passes(self):
        response = self.client.get("/privacy/", HTTP_USER_AGENT="Mozilla/5.0")
        self.assertEqual(response.status_code, 200)

    def test_scraper_block_switch(self):
        fresh_config(enable_scraper_block=False)
        response = self.client.get("/privacy/", HTTP_USER_AGENT="curl/8.0")
        self.assertEqual(response.status_code, 200)
        fresh_config(enable_scraper_block=True)


class ProtectedPageTests(ConfigIsolatedTestCase):
    def test_protected_path_redirects_anonymous_to_login(self):
        ProtectedPage.objects.create(path="/account/", match_type=ProtectedPage.MATCH_PREFIX, title="your account")
        response = self.client.get("/account/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertIn("next=/account/", response["Location"])

    def test_protected_path_allows_authenticated_user(self):
        ProtectedPage.objects.create(path="/account/", match_type=ProtectedPage.MATCH_PREFIX, title="your account")
        user = User.objects.create_user(username="member", password="S3cure!pass")
        self.client.force_login(user)
        response = self.client.get("/account/")
        self.assertEqual(response.status_code, 200)

    def test_inactive_page_rule_is_ignored(self):
        ProtectedPage.objects.create(path="/account/", match_type=ProtectedPage.MATCH_PREFIX, active=False)
        response = self.client.get("/account/")
        self.assertEqual(response.status_code, 302)  # login_required on the view itself


class RegistrationSwitchTests(ConfigIsolatedTestCase):
    def test_registration_available_by_default(self):
        self.assertEqual(self.client.get("/accounts/register/").status_code, 200)

    def test_registration_disabled_redirects_to_login(self):
        fresh_config(enable_public_registration=False)
        response = self.client.get("/accounts/register/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        fresh_config(enable_public_registration=True)

    def test_registration_creates_active_user(self):
        payload = {
            "username": "newuser",
            "email": "new@example.com",
            "password1": "correct-horse-battery-99",
            "password2": "correct-horse-battery-99",
        }
        response = self.client.post("/accounts/register/", payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser", is_active=True).exists())

    def test_registration_with_approval_creates_inactive_user(self):
        fresh_config(registration_requires_approval=True)
        payload = {
            "username": "waiting",
            "email": "wait@example.com",
            "password1": "correct-horse-battery-99",
            "password2": "correct-horse-battery-99",
        }
        self.client.post("/accounts/register/", payload)
        self.assertTrue(User.objects.filter(username="waiting", is_active=False).exists())
        fresh_config(registration_requires_approval=False)


class ContactDefenseTests(ConfigIsolatedTestCase):
    def base_payload(self):
        return {
            "name": "Tester",
            "email": "tester@example.com",
            "phone": "",
            "preference": "email",
            "message": "A sufficiently long message for the test.",
            "website": "",
            "form_ts": signing.dumps(0, salt=FORM_TS_SALT),
            "consent": "on",
        }

    def test_valid_submission_stores_message(self):
        response = self.client.post("/contact/", self.base_payload())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/contact/thanks/", response["Location"])
        self.assertTrue(ContactMessage.objects.filter(email="tester@example.com").exists())

    def test_honeypot_silently_discards(self):
        payload = self.base_payload()
        payload["website"] = "http://spam.example"
        response = self.client.post("/contact/", payload)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ContactMessage.objects.exists())

    def test_missing_form_ts_discards(self):
        payload = self.base_payload()
        payload["form_ts"] = "garbage"
        self.client.post("/contact/", payload)
        self.assertFalse(ContactMessage.objects.exists())

    def test_rate_limit_blocks_second_submission(self):
        self.client.post("/contact/", self.base_payload())
        response = self.client.post("/contact/", self.base_payload(), follow=True)
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("another message" in str(m) for m in messages))

    def test_contact_form_switch(self):
        fresh_config(enable_contact_form=False)
        response = self.client.get("/contact/")
        self.assertEqual(response.status_code, 302)
        fresh_config(enable_contact_form=True)


class ExternalLinkMiddlewareTests(ConfigIsolatedTestCase):
    def test_outbound_links_get_snatched(self):
        html = self.client.get("/demo/").content.decode()
        self.assertIn('data-external="true"', html)
        self.assertIn("noopener noreferrer", html)
        # utm_source derives from the configured canonical_origin (host only, no port)
        self.assertIn("utm_source=127-0-0-1\"", html)

    def test_snatcher_can_be_disabled(self):
        fresh_config(enable_external_link_handling=False)
        html = self.client.get("/demo/").content.decode()
        self.assertNotIn('data-external="true"', html)
        fresh_config(enable_external_link_handling=True)

    def test_modal_script_only_when_enabled(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn("external-link-modal.js", html)
        fresh_config(external_link_modal=True)
        html = self.client.get("/").content.decode()
        self.assertIn("external-link-modal.js", html)
        fresh_config(external_link_modal=False)


class SeedCommandTests(TestCase):
    @override_settings(SEED_ADMIN_USERNAME="admin", SEED_ADMIN_PASSWORD="b_4sIcPW007")
    def test_seed_creates_superuser_and_defaults(self):
        from django.core.management import call_command

        call_command("seed", verbosity=0)
        self.assertTrue(User.objects.filter(username="admin", is_superuser=True).exists())
        self.assertTrue(ProtectedPage.objects.filter(path="/account/").exists())
        # Idempotent: second run must not explode or duplicate.
        call_command("seed", verbosity=0)
        self.assertEqual(User.objects.filter(username="admin").count(), 1)
