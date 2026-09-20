"""Smoke tests: every mechanism in the skeleton has at least one assertion
that proves its control-panel switch actually changes behavior."""

import io
import tempfile

from django.utils import timezone

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from django_otp.oath import TOTP as TotpGenerator
from django_otp.plugins.otp_totp.models import TOTPDevice


def device_token(device):
    import time

    generator = TotpGenerator(device.bin_key)
    generator.time = time.time()
    return generator.token()

from core.models import (
    Article,
    CONFIG_CACHE_KEY,
    ContactMessage,
    FooterItem,
    NavigationItem,
    ProtectedPage,
    RobotsRule,
    SiteConfiguration,
)
from core import bootstrap
from core.views.contact import FORM_TS_SALT

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


class PageSmokeTests(ConfigIsolatedTestCase):
    def test_public_pages_render(self):
        for url in ["/", "/demo/", "/articles/", "/contact/"]:
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
            "/humans.txt": "django-skeleton",
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

    def test_demo_places_scroll_reveal_after_other_mechanisms(self):
        html = self.client.get("/demo/").content.decode()
        self.assertLess(html.index('id="demo-hero-entrance"'), html.index('id="demo-reveal"'))
        self.assertLess(html.index('id="demo-lottie"'), html.index('id="demo-reveal"'))

    def test_print_control_uses_csp_safe_handler(self):
        html = self.client.get("/").content.decode()
        self.assertIn('data-a11y-action="print-page"', html)
        self.assertNotIn("onclick=", html)


class ConsentAndTrackingTests(ConfigIsolatedTestCase):
    def test_consent_assets_present_when_enabled(self):
        html = self.client.get("/").content.decode()
        self.assertIn("klaro-config.js", html)
        self.assertIn("skeleton-tracking-config", html)
        self.assertLess(html.index("klaro-config.js"), html.index("vendor/klaro/klaro.js"))
        self.assertLess(html.index("vendor/klaro/klaro.js"), html.index("klaro-bootstrap.js"))
        self.assertNotIn('data-cmp-root', html)

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
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("sitemap.xml", self.client.get("/").content.decode())
        fresh_config(enable_sitemap=True)

    def test_robots_rules_and_switch(self):
        RobotsRule.objects.create(path="/private-library/", active=True, sort_order=1)
        content = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /private-library/", content)
        self.assertIn("Disallow: /static/", content)
        self.assertIn("Disallow: /privacy/", content)
        fresh_config(enable_robots_txt=False)
        self.assertEqual(self.client.get("/robots.txt").status_code, 404)
        self.assertNotIn('href="/robots.txt"', self.client.get("/").content.decode())

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
        # blocked scrapers get the uniform 404 page: production behavior,
        # since the test runner forces DEBUG=False
        response = self.client.get("/privacy/", HTTP_USER_AGENT="curl/8.0")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Nothing at this address", response.content.decode())

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

    def test_registration_disabled_returns_not_found(self):
        fresh_config(enable_public_registration=False)
        response = self.client.get("/accounts/register/")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('href="/accounts/register/"', self.client.get("/accounts/login/").content.decode())
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
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get("/contact/thanks/").status_code, 404)
        self.assertNotIn('href="/contact/"', self.client.get("/").content.decode())
        fresh_config(enable_contact_form=True)


class ArticleSwitchTests(ConfigIsolatedTestCase):
    def setUp(self):
        super().setUp()
        self.article = Article.objects.create(
            title="A field note",
            slug="a-field-note",
            content="First paragraph.\n\nSecond paragraph.",
            meta_description="A short description for search results.",
            excerpt="A concise article summary.",
            published=True,
        )

    def test_article_index_and_detail_render(self):
        self.assertContains(self.client.get("/articles/"), "A field note")
        self.assertContains(self.client.get("/articles/a-field-note/"), "Second paragraph")
        self.assertIn("/articles/", self.client.get("/sitemap.xml").content.decode())

    def test_article_switch_removes_every_public_reference(self):
        fresh_config(enable_articles=False)
        self.assertEqual(self.client.get("/articles/").status_code, 404)
        self.assertEqual(self.client.get("/articles/a-field-note/").status_code, 404)
        self.assertNotIn('href="/articles/"', self.client.get("/").content.decode())
        self.assertNotIn("/articles/", self.client.get("/sitemap.xml").content.decode())
        self.assertNotIn("/articles/", self.client.get("/llms.txt").content.decode())

    def test_draft_article_is_private(self):
        self.article.published = False
        self.article.save()
        self.assertEqual(self.client.get("/articles/a-field-note/").status_code, 404)

    def test_article_admin_loads_drag_and_drop_editor(self):
        admin = User.objects.get(username="admin")
        self.client.force_login(admin)
        response = self.client.get("/admin/core/article/add/")
        self.assertContains(response, "admin-image-drop.js")
        self.assertContains(response, 'name="meta_description"')
        self.assertContains(response, "Article images")


class FooterSwitchTests(ConfigIsolatedTestCase):
    def test_quiet_syntaxsavr_credit_is_seeded(self):
        html = self.client.get("/").content.decode()
        self.assertIn("footer-item-quiet", html)
        self.assertIn("https://github.com/syntaxsavr", html)

    def test_footer_can_be_removed(self):
        self.assertContains(self.client.get("/"), 'class="site-footer"')
        fresh_config(enable_footer=False)
        self.assertNotContains(self.client.get("/"), 'class="site-footer"')


class HeaderNavigationTests(ConfigIsolatedTestCase):
    def test_megamenu_renders_configured_groups_and_mobile_toggle(self):
        response = self.client.get("/")
        self.assertContains(response, "data-mega-menu")
        self.assertContains(response, 'class="megamenu-title">Explore')
        self.assertContains(response, "data-nav-toggle")
        self.assertContains(response, 'aria-controls="site-navigation"')

    def test_megamenu_switch_restores_compact_navigation(self):
        fresh_config(enable_megamenu=False)
        response = self.client.get("/")
        self.assertNotContains(response, "data-mega-menu")
        self.assertContains(response, 'class="site-nav"')
        self.assertContains(response, "data-nav-toggle")

    def test_configured_item_and_uploaded_logo_render(self):
        config = fresh_config(header_logo="navigation/mark.png", header_logo_alt="Skeleton mark")
        NavigationItem.objects.create(
            site_configuration=config,
            group="Work",
            label="Case studies",
            description="Selected project notes.",
            page=NavigationItem.PAGE_CUSTOM,
            url="/work/",
            sort_order=5,
        )
        response = self.client.get("/")
        self.assertContains(response, 'src="/media/navigation/mark.png"')
        self.assertContains(response, 'alt="Skeleton mark"')
        self.assertContains(response, "Case studies")
        self.assertContains(response, "Selected project notes.")

    def test_logo_switch_uses_site_name_fallback(self):
        fresh_config(
            enable_header_logo=False,
            header_logo="navigation/mark.png",
            header_logo_alt="Skeleton mark",
        )
        response = self.client.get("/")
        self.assertNotContains(response, "/media/navigation/mark.png")
        self.assertContains(response, "skeleton")

    def test_feature_bound_megamenu_item_disappears(self):
        self.assertContains(self.client.get("/"), 'href="/articles/"')
        fresh_config(enable_articles=False)
        self.assertNotContains(self.client.get("/"), 'href="/articles/"')

    def test_site_configuration_admin_contains_logo_and_navigation_editor(self):
        admin = User.objects.get(username="admin")
        self.client.force_login(admin)
        response = self.client.get("/admin/core/siteconfiguration/1/change/")
        self.assertContains(response, 'name="header_logo"')
        self.assertContains(response, 'name="enable_megamenu"')
        self.assertContains(response, "Navigation items")


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

    def test_modal_script_enabled_by_default_and_switchable(self):
        html = self.client.get("/").content.decode()
        self.assertIn("external-link-modal.js", html)
        fresh_config(external_link_modal=False)
        html = self.client.get("/").content.decode()
        self.assertNotIn("external-link-modal.js", html)
        fresh_config(external_link_modal=True)


class SeedCommandTests(TestCase):
    @override_settings(SEED_ADMIN_USERNAME="admin", SEED_ADMIN_PASSWORD="b_4sIcPW007")
    def test_seed_creates_superuser_and_defaults(self):
        from django.core.management import call_command

        User.objects.filter(username="admin").delete()
        call_command("seed", verbosity=0)
        admin = User.objects.get(username="admin", is_superuser=True)
        self.assertTrue(admin.check_password("b_4sIcPW007"))
        self.assertTrue(ProtectedPage.objects.filter(path="/account/").exists())
        # Idempotent: second run must not explode or duplicate.
        call_command("seed", verbosity=0)
        self.assertEqual(User.objects.filter(username="admin").count(), 1)


class AccessibilityPanelTests(ConfigIsolatedTestCase):
    def test_a11y_button_and_panel_render_by_default(self):
        html = self.client.get("/").content.decode()
        self.assertIn('data-modal-open="a11y-modal"', html)
        self.assertIn('id="a11y-modal"', html)
        self.assertIn("toggle-contrast", html)

    def test_a11y_button_can_be_disabled(self):
        fresh_config(enable_accessibility_panel=False)
        html = self.client.get("/").content.decode()
        self.assertNotIn("a11y-button", html)
        self.assertNotIn('id="a11y-modal"', html)

    def test_footer_no_longer_seeds_display_items(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn('<span class="mono-label">Display</span>', html)
        bootstrap.ensure_starter_content()
        self.assertFalse(FooterItem.objects.filter(action__in=["dark", "text_size", "motion", "print"]).exists())


class AnnouncementBannerTests(ConfigIsolatedTestCase):
    def test_announcement_off_by_default(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn("announcement-bar", html)

    def test_announcement_renders_when_enabled(self):
        fresh_config(enable_announcement=True, announcement_text="Open house on Friday", announcement_url="/demo/")
        html = self.client.get("/").content.decode()
        self.assertIn("announcement-bar", html)
        self.assertIn("Open house on Friday", html)
        self.assertIn('href="/demo/"', html)

    def test_announcement_without_text_stays_hidden(self):
        fresh_config(enable_announcement=True)
        self.assertNotIn("announcement-bar", self.client.get("/").content.decode())


@override_settings(ENFORCE_STAFF_2FA=True)
class Staff2FAEnforcementTests(TestCase):
    def setUp(self):
        cache.clear()
        SiteConfiguration.get_solo()
        self.staff = User.objects.create_user("boss", "boss@example.com", "S3cure!pass", is_staff=True)

    def login_staff(self):
        self.assertTrue(self.client.login(username="boss", password="S3cure!pass"))

    def test_admin_redirects_staff_without_verified_device(self):
        self.login_staff()
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/two-factor/setup/", response["Location"])

    def test_public_pages_unaffected_for_staff_without_device(self):
        self.login_staff()
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_admin_logout_stays_reachable(self):
        self.login_staff()
        response = self.client.post("/admin/logout/")
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("two-factor", response["Location"])

    def test_setup_shows_qr_and_secret_and_activates_device(self):
        import base64

        self.login_staff()
        response = self.client.get("/account/two-factor/setup/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("data:image/png;base64,", response.content.decode())
        device = TOTPDevice.objects.get(user=self.staff)
        secret = base64.b32encode(bytes.fromhex(device.key)).decode().rstrip("=")
        self.assertIn(secret, response.content.decode())
        token = device_token(device)
        response = self.client.post("/account/two-factor/setup/", {"token": token})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/", response["Location"])
        device.refresh_from_db()
        self.assertTrue(device.confirmed)

    def test_verified_staff_reaches_admin(self):
        self.login_staff()
        device = TOTPDevice.objects.create(user=self.staff, name="Authenticator", confirmed=True)
        self.client.post("/account/two-factor/verify/", {"token": device_token(device)})
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_verify_with_wrong_code_stays_locked(self):
        self.login_staff()
        TOTPDevice.objects.create(user=self.staff, name="Authenticator", confirmed=True)
        response = self.client.post("/account/two-factor/verify/", {"token": "000000"}, follow=True)
        self.assertContains(response, "did not match")
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_removal_relocks_admin(self):
        self.login_staff()
        TOTPDevice.objects.create(user=self.staff, name="Authenticator", confirmed=True)
        self.client.post("/account/two-factor/verify/", {"token": device_token(TOTPDevice.objects.get())})
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.client.post("/account/two-factor/remove/")
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/two-factor/setup/", response["Location"])


class Staff2FAOffInDebugTests(ConfigIsolatedTestCase):
    def test_admin_reachable_without_second_factor_when_not_enforced(self):
        staff = User.objects.create_user("relax", "relax@example.com", "S3cure!pass", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/admin/").status_code, 200)


class TwoFactorOptionalForNonStaffTests(ConfigIsolatedTestCase):
    def test_non_staff_can_browse_without_any_device(self):
        User.objects.create_user("member", "member@example.com", "S3cure!pass")
        self.assertTrue(self.client.login(username="member", password="S3cure!pass"))
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_non_staff_can_voluntarily_manage(self):
        member = User.objects.create_user("member", "member@example.com", "S3cure!pass")
        self.client.force_login(member)
        response = self.client.get("/account/two-factor/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Set up two-factor", response.content.decode())


class ArticleBlockTests(ConfigIsolatedTestCase):
    def _article(self, **kwargs):
        defaults = {"title": "Blocks article", "slug": "blocks-article", "excerpt": "About blocks.",
                    "meta_description": "Blocks meta", "content": "Legacy fallback text.", "published": True}
        defaults.update(kwargs)
        return Article.objects.create(**defaults)

    def test_blocks_render_in_order_and_legacy_fallback(self):
        from core.models import ArticleBlock
        article = self._article()
        ArticleBlock.objects.create(article=article, kind="heading", text="First heading", heading_level="2", sort_order=10)
        ArticleBlock.objects.create(article=article, kind="text", text="Block body text.", sort_order=20)
        html = self.client.get("/articles/blocks-article/").content.decode()
        self.assertIn("First heading", html)
        self.assertIn("Block body text.", html)
        self.assertNotIn("Legacy fallback text.", html)

        from core.models import ArticleBlock as B
        B.objects.all().delete()
        html = self.client.get("/articles/blocks-article/").content.decode()
        self.assertIn("Legacy fallback text.", html)

    def test_preview_requires_staff(self):
        response = self.client.post("/articles/preview/", {"title": "x"})
        self.assertEqual(response.status_code, 302)  # redirected to admin login
        staff = User.objects.get(username="admin")
        self.client.force_login(staff)
        response = self.client.post("/articles/preview/", {"title": "Preview me", "inline_prefix": "blocks", "blocks-TOTAL_FORMS": "0"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Preview me", response.content.decode())

    def test_preview_renders_submitted_blocks(self):
        staff = User.objects.get(username="admin")
        self.client.force_login(staff)
        payload = {
            "title": "Preview blocks",
            "inline_prefix": "blocks",
            "blocks-TOTAL_FORMS": "2",
            "blocks-INITIAL_FORMS": "0",
            "blocks-0-kind": "heading",
            "blocks-0-text": "Submitted heading",
            "blocks-1-kind": "quote",
            "blocks-1-text": "A wise quote",
            "blocks-1-quote_attribution": "Someone",
        }
        response = self.client.post("/articles/preview/", payload)
        html = response.content.decode()
        self.assertIn("Preview blocks", html)
        self.assertIn("Submitted heading", html)
        self.assertIn("A wise quote", html)
        self.assertIn("Someone", html)

    def test_youtube_embed_url_parsing(self):
        from core.models import ArticleBlock
        article = self._article(slug="video-article")
        block = ArticleBlock.objects.create(article=article, kind="video", video_url="https://youtu.be/dQw4w9WgXcQ?si=x")
        self.assertEqual(block.video_provider, "youtube")
        self.assertTrue(block.video_embed_url.startswith("https://www.youtube-nocookie.com/embed/"))
        html = self.client.get("/articles/video-article/").content.decode()
        self.assertIn("youtube-nocookie.com/embed", html)


class ConsentMediaTests(ConfigIsolatedTestCase):
    def _video_article(self):
        from core.models import ArticleBlock
        article = Article.objects.create(
            title="Consent video", slug="consent-video", excerpt="e", meta_description="m",
            content="c", published=True,
        )
        ArticleBlock.objects.create(article=article, kind="video", video_url="https://vimeo.com/76979871")
        return article

    def test_external_video_gated_when_consent_on(self):
        self._video_article()
        fresh_config(enable_cookie_consent=True)
        html = self.client.get("/articles/consent-video/").content.decode()
        self.assertIn('data-consent-embed="vimeo"', html)
        self.assertIn("Load Vimeo video", html)
        self.assertNotIn("<iframe", html)

    def test_external_video_direct_when_consent_off(self):
        self._video_article()
        fresh_config(enable_cookie_consent=False)
        html = self.client.get("/articles/consent-video/").content.decode()
        self.assertIn("player.vimeo.com/video", html)
        self.assertNotIn("Load Vimeo video", html)

    def test_consent_media_script_present_for_articles(self):
        self._video_article()
        html = self.client.get("/articles/consent-video/").content.decode()
        self.assertIn("consent-media.js", html)


class WebpConversionTests(ConfigIsolatedTestCase):
    def _upload(self):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (40, 30), (200, 40, 40)).save(buffer, format="JPEG")
        return SimpleUploadedFile("photo.jpg", buffer.getvalue(), content_type="image/jpeg")

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_image_converts_to_webp_when_enabled(self):
        from core.models import ArticleImage

        fresh_config(enable_webp_conversion=True, webp_quality=70)
        article = Article.objects.create(title="Webp", slug="webp", excerpt="e", meta_description="m", published=True)
        entry = ArticleImage.objects.create(article=article, image=self._upload(), alt_text="red square")
        self.assertTrue(entry.image.name.endswith(".webp"), entry.image.name)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_image_stays_jpeg_when_disabled(self):
        from core.models import ArticleImage

        fresh_config(enable_webp_conversion=False)
        article = Article.objects.create(title="Jpg", slug="jpg", excerpt="e", meta_description="m", published=True)
        entry = ArticleImage.objects.create(article=article, image=self._upload(), alt_text="red square")
        self.assertTrue(entry.image.name.endswith(".jpg"), entry.image.name)


class StripeMultiButtonTests(ConfigIsolatedTestCase):
    def _article_with_button(self):
        from core.models import ArticleBlock, StripeButton
        button = StripeButton.objects.create(label="Audit", buy_button_id="buy_test_123", sort_order=10)
        article = Article.objects.create(title="Buy", slug="buy-article", excerpt="e", meta_description="m", published=True)
        ArticleBlock.objects.create(article=article, kind="buy", buy_button=button)
        second = StripeButton.objects.create(label="Retainer", buy_button_id="buy_test_456", sort_order=20)
        return article, button, second

    def test_multiple_buttons_render_in_articles(self):
        fresh_config(enable_stripe_buy_button=True, stripe_publishable_key="pk_test_123")
        article, button, second = self._article_with_button()
        html = self.client.get("/articles/buy-article/").content.decode()
        self.assertIn('data-buy-button-id="buy_test_123"', html)

    def test_master_switch_gates_buy_blocks(self):
        button_config = fresh_config(enable_stripe_buy_button=False)
        self._article_with_button()
        html = self.client.get("/articles/buy-article/").content.decode()
        self.assertNotIn("data-buy-button-id", html)

    def test_csp_allows_video_frames_for_articles(self):
        config = fresh_config(enable_articles=True)
        policy = self.client.get("/")["Content-Security-Policy"]
        self.assertIn("youtube-nocookie.com", policy)
        self.assertIn("player.vimeo.com", policy)


@override_settings(DEBUG=False)
class ProductionErrorUniformityTests(TestCase):
    def test_every_error_displays_the_404_page(self):
        for url, follow in [("/no-such-page/", False)]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)
                self.assertIn("Nothing at this address", response.content.decode())

    def test_forbidden_renders_as_404_in_prod(self):
        response = self.client.get("/privacy/", HTTP_USER_AGENT="curl/8.0")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Nothing at this address", response.content.decode())
        # the handler renders the uniform page even though the scraper
        # block middleware produced a 403

    def test_error_padding_has_random_length_up_to_512(self):
        import re

        lengths = set()
        for _ in range(12):
            html = self.client.get("/no-such-page/").content.decode()
            match = re.search(r'<span class="error-noise" hidden>([^<]*)</span>', html)
            self.assertIsNotNone(match)
            lengths.add(len(match.group(1)))
        self.assertGreater(len(lengths), 2)  # random, not constant
        self.assertLessEqual(max(lengths), 512)

    def test_debug_keeps_distinct_codes(self):
        from django.test.utils import override_settings as override

        with override(DEBUG=True):
            self.assertEqual(self.client.get("/no-such-page/").status_code, 404)


class MessageRetentionTests(ConfigIsolatedTestCase):
    def _make_message(self, days_old):
        from datetime import timedelta

        from core.models import ContactMessage

        message = ContactMessage.objects.create(
            name="Old", email="old@example.com", message="hello"
        )
        ContactMessage.objects.filter(pk=message.pk).update(
            created=timezone.now() - timedelta(days=days_old)
        )
        return message

    def test_purge_removes_only_old_messages(self):
        from core.maintenance import purge_old_messages

        old = self._make_message(40)
        fresh = self._make_message(2)
        config = fresh_config(enable_message_auto_delete=True, message_retention_days=30)
        removed = purge_old_messages()
        self.assertEqual(removed, 1)
        self.assertFalse(ContactMessage.objects.filter(pk=old.pk).exists())
        self.assertTrue(ContactMessage.objects.filter(pk=fresh.pk).exists())

    def test_switch_disables_purge(self):
        from core.maintenance import purge_if_due

        fresh_config(enable_message_auto_delete=False)
        self._make_message(400)
        self.assertEqual(purge_if_due(), 0)

    def test_lazy_trigger_runs_daily_and_respects_window(self):
        from core.maintenance import purge_if_due

        fresh_config(enable_message_auto_delete=True, message_retention_days=30)
        self._make_message(31)
        self.assertEqual(purge_if_due(), 1)
        self._make_message(31)
        self.assertEqual(purge_if_due(), 0)  # ran today already

    def test_purge_command(self):
        from django.core.management import call_command

        self._make_message(31)
        out = io.StringIO()
        call_command("purge_messages", stdout=out)
        self.assertIn("Removed 1", out.getvalue())


class EmailOtpTests(ConfigIsolatedTestCase):
    def _register(self):
        from django.core.mail import outbox

        payload = {
            "username": "otpgal",
            "email": "gal@example.com",
            "password1": "correct-horse-battery-99",
            "password2": "correct-horse-battery-99",
        }
        response = self.client.post("/accounts/register/", payload)
        return response, outbox

    def test_otp_flow_activates_account(self):
        import re

        fresh_config(enable_email_otp=True)
        response, outbox = self._register()
        self.assertEqual(response.status_code, 302)
        self.assertIn("confirm", response["Location"])
        user = User.objects.get(username="otpgal")
        self.assertFalse(user.is_active)
        # code arrived by mail (locmem backend; console backend in real DEBUG)
        codes = re.findall(r"\b(\d{6})\b", "\n".join(m.body for m in outbox))
        self.assertTrue(codes)
        response = self.client.post("/accounts/register/confirm/", {"code": codes[0]})
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_wrong_code_stays_inactive(self):
        fresh_config(enable_email_otp=True)
        self._register()
        self.client.post("/accounts/register/confirm/", {"code": "000000"})
        self.assertFalse(User.objects.get(username="otpgal").is_active)

    def test_otp_off_keeps_direct_activation(self):
        fresh_config(enable_email_otp=False)
        response, outbox = self._register()
        self.assertTrue(User.objects.get(username="otpgal").is_active)
        self.assertEqual(len(outbox), 0)

    def test_confirm_page_needs_session(self):
        self.assertEqual(self.client.get("/accounts/register/confirm/").status_code, 302)


class PasswordMinimumTests(TestCase):
    def test_short_passwords_rejected(self):
        payload = {
            "username": "shorty",
            "email": "short@example.com",
            "password1": "ab12cd3",
            "password2": "ab12cd3",
        }
        response = self.client.post("/accounts/register/", payload, follow=True)
        self.assertContains(response, "at least 8 characters")
