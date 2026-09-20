"""Data models for the skeleton core.

Three models carry the whole control-panel idea:

SiteConfiguration  single-row settings object; the admin panel is the UI.
ProtectedPage      login-wall rule evaluated by core.middleware.
ContactMessage     contact form submissions.
"""

from django.conf import settings
from django.core.cache import cache
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

CONFIG_CACHE_KEY = "core:site_configuration:solo"
CONFIG_CACHE_TTL = 60


def _env_or(env_name: str, fallback: str) -> str:
    """Environment wins over the DB so production secrets never need the admin."""
    value = getattr(settings, env_name, "")
    return value or fallback


class SiteConfiguration(models.Model):
    """The control panel. One row (pk=1), edited in the admin, read everywhere."""

    # --- Site identity ------------------------------------------------------
    site_name = models.CharField(max_length=120, default="Skeleton")
    canonical_origin = models.CharField(
        max_length=200,
        default="http://127.0.0.1:8000",
        help_text="Used for canonical URLs, hreflang, JSON-LD, sitemap, IndexNow. No trailing slash.",
    )
    contact_email = models.EmailField(blank=True)
    default_meta_description = models.CharField(
        max_length=300,
        blank=True,
        default="A production-shaped Django skeleton: consent-first tracking, SEO suite, lazy sections, Lottie.",
    )
    theme_color = models.CharField(max_length=9, default="#fcfcfa")

    # --- Consent & tracking --------------------------------------------------
    enable_cookie_consent = models.BooleanField(
        default=True, help_text="Master switch for the Klaro! consent manager and banner."
    )
    consent_cookie_name = models.CharField(max_length=64, default="skeleton_consent")
    enable_tracking = models.BooleanField(
        default=False,
        help_text="Master switch. A tracker loads only when this is on AND its ID below is filled in.",
    )
    google_tag_manager_id = models.CharField(max_length=32, blank=True)
    google_analytics_measurement_id = models.CharField(max_length=32, blank=True)
    google_ads_id = models.CharField(max_length=32, blank=True)
    google_ads_conversion_label = models.CharField(max_length=64, blank=True)
    meta_pixel_id = models.CharField(max_length=64, blank=True)
    linkedin_partner_id = models.CharField(max_length=32, blank=True)
    microsoft_ads_uet_tag_id = models.CharField(max_length=64, blank=True)
    microsoft_clarity_project_id = models.CharField(max_length=32, blank=True)
    hotjar_site_id = models.CharField(max_length=16, blank=True)
    tiktok_pixel_id = models.CharField(max_length=64, blank=True)
    pinterest_tag_id = models.CharField(max_length=32, blank=True)
    x_twitter_pixel_id = models.CharField(max_length=32, blank=True)
    matomo_url = models.CharField(
        max_length=200, blank=True, help_text="Self-hosted Matomo base URL, e.g. https://analytics.example.com"
    )
    matomo_site_id = models.CharField(max_length=8, blank=True)

    # --- SEO ------------------------------------------------------------------
    enable_sitemap = models.BooleanField(default=True)
    enable_robots_txt = models.BooleanField(default=True)
    enable_llms_txt = models.BooleanField(default=True, help_text="Serves /llms.txt and /llms-full.txt for AI crawlers.")
    enable_jsonld = models.BooleanField(default=True)
    enable_indexnow = models.BooleanField(default=False)
    indexnow_key = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="IndexNow key. The <key>.txt proof route only matches this value.",
    )
    google_site_verification = models.CharField(max_length=128, blank=True)
    bing_site_verification = models.CharField(max_length=128, blank=True)
    facebook_domain_verification = models.CharField(max_length=128, blank=True)
    pinterest_domain_verification = models.CharField(max_length=128, blank=True)
    robots_noindex_whole_site = models.BooleanField(
        default=False, help_text="Staging kill switch: X-Robots-Tag noindex on every page."
    )

    # --- Forms & anti-spam ------------------------------------------------------
    enable_contact_form = models.BooleanField(default=True)
    enable_turnstile = models.BooleanField(
        default=False, help_text="Cloudflare Turnstile on the contact form. Keys come from env or the fields below."
    )
    turnstile_site_key = models.CharField(max_length=128, blank=True)
    turnstile_secret_key = models.CharField(max_length=128, blank=True)
    enable_honeypot = models.BooleanField(default=True)
    form_min_seconds = models.PositiveIntegerField(
        default=3, help_text="Signed time-trap: bots that submit faster are silently discarded."
    )
    contact_rate_limit_seconds = models.PositiveIntegerField(
        default=300, validators=[MinValueValidator(10)],
        help_text="Per-session cooldown between contact form submissions.",
    )

    # --- Auth -------------------------------------------------------------------
    enable_public_registration = models.BooleanField(default=True)
    registration_requires_approval = models.BooleanField(
        default=False,
        help_text="New users are created inactive; an admin activates them in People.",
    )

    # --- Embeds -------------------------------------------------------------------
    enable_calcom_embed = models.BooleanField(default=False)
    calcom_link = models.CharField(max_length=200, blank=True)
    enable_stripe_buy_button = models.BooleanField(default=False)
    stripe_publishable_key = models.CharField(max_length=128, blank=True)
    stripe_buy_button_id = models.CharField(max_length=128, blank=True)

    # --- Middleware switches ---------------------------------------------------------
    enable_scraper_block = models.BooleanField(
        default=True, help_text="403 known scraper user agents on legal/personal-data pages."
    )
    enable_csp = models.BooleanField(default=True, help_text="Content-Security-Policy header (skipped on /admin/).")
    enable_external_link_handling = models.BooleanField(
        default=True,
        help_text="Outbound link snatcher: tags external anchors with data-external + rel=noopener noreferrer.",
    )
    external_link_utm = models.BooleanField(
        default=True, help_text="Append utm_source=<your host> to outbound links."
    )
    external_link_modal = models.BooleanField(
        default=False, help_text="Show the leave-site confirmation modal for outbound clicks."
    )

    class Meta:
        verbose_name = "Site configuration"
        verbose_name_plural = "Site configuration"

    def __str__(self) -> str:
        return f"{self.site_name} configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(CONFIG_CACHE_KEY)

    def delete(self, *args, **kwargs):  # pragma: no cover - singleton guard
        cache.delete(CONFIG_CACHE_KEY)

    @classmethod
    def get_solo(cls) -> "SiteConfiguration":
        config = cache.get(CONFIG_CACHE_KEY)
        if config is None:
            config = cls.objects.get_or_create(pk=1)[0]
            cache.set(CONFIG_CACHE_KEY, config, CONFIG_CACHE_TTL)
        return config

    @property
    def effective_turnstile_site_key(self) -> str:
        return _env_or("TURNSTILE_SITE_KEY", self.turnstile_site_key or "")

    @property
    def effective_turnstile_secret_key(self) -> str:
        return _env_or("TURNSTILE_SECRET_KEY", self.turnstile_secret_key or "")

    def tracking_data(self) -> dict:
        """JSON-safe payload rendered via json_script and read by the consent
        manager. Empty ID means the tracker is not declared at all."""
        if not self.enable_tracking:
            ids = {}
        else:
            ids = {
                "googleTagManagerId": self.google_tag_manager_id.strip(),
                "googleAnalyticsId": self.google_analytics_measurement_id.strip(),
                "googleAdsId": self.google_ads_id.strip(),
                "googleAdsConversionLabel": self.google_ads_conversion_label.strip(),
                "metaPixelId": self.meta_pixel_id.strip(),
                "linkedinPartnerId": self.linkedin_partner_id.strip(),
                "microsoftUetTagId": self.microsoft_ads_uet_tag_id.strip(),
                "clarityProjectId": self.microsoft_clarity_project_id.strip(),
                "hotjarSiteId": self.hotjar_site_id.strip(),
                "tiktokPixelId": self.tiktok_pixel_id.strip(),
                "pinterestTagId": self.pinterest_tag_id.strip(),
                "xPixelId": self.x_twitter_pixel_id.strip(),
                "matomoUrl": self.matomo_url.strip().rstrip("/"),
                "matomoSiteId": self.matomo_site_id.strip(),
            }
        return {
            "consentEnabled": self.enable_cookie_consent,
            "trackingEnabled": self.enable_tracking,
            "storageName": self.consent_cookie_name,
            "privacyPolicyUrl": reverse("privacy"),
            "ids": ids,
            "calcom": {"enabled": self.enable_calcom_embed, "link": self.calcom_link.strip()},
            "stripe": {
                "enabled": self.enable_stripe_buy_button,
                "publishableKey": self.stripe_publishable_key.strip(),
                "buyButtonId": self.stripe_buy_button_id.strip(),
            },
            "turnstileSiteKey": self.effective_turnstile_site_key if self.enable_turnstile else "",
        }


class ProtectedPage(models.Model):
    """Put a path behind login. Evaluated by core.middleware.ProtectedPageMiddleware."""

    MATCH_EXACT = "exact"
    MATCH_PREFIX = "prefix"
    MATCH_CHOICES = ((MATCH_EXACT, "Exact path"), (MATCH_PREFIX, "Path prefix"))

    path = models.CharField(
        max_length=200,
        help_text="No leading domain. Examples: /account/ (prefix) or /board/report.pdf (exact).",
    )
    match_type = models.CharField(max_length=10, choices=MATCH_CHOICES, default=MATCH_PREFIX)
    title = models.CharField(
        max_length=120,
        blank=True,
        help_text="Shown on the login page ('you need to sign in to view <title>').",
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["path"]

    def __str__(self) -> str:
        return f"{self.path} ({self.get_match_type_display()})"


class ContactMessage(models.Model):
    PREFERENCE_CHOICES = (
        ("email", "Reply by email"),
        ("call", "Call me back"),
    )
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    preference = models.CharField(max_length=10, choices=PREFERENCE_CHOICES, default="email")
    message = models.TextField()
    responded = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created"]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"
