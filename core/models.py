"""Data models for the skeleton core.

The models carry the whole control-panel idea:

SiteConfiguration  single-row settings object; the admin panel is the UI.
ProtectedPage      login-wall rule evaluated by core.middleware.
ContactMessage     contact form submissions.
Article            optional editorial content.
RobotsRule         editable robots.txt path rules.
FooterSection      ordered footer columns.
FooterItem         feature-aware links, actions, text and media.
NavigationItem     ordered, feature-aware header and megamenu links.
"""

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

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

    # --- Media -----------------------------------------------------------------
    enable_webp_conversion = models.BooleanField(
        default=True,
        help_text="Newly uploaded article images are automatically stored as WebP.",
    )
    webp_quality = models.PositiveSmallIntegerField(default=82)

    # --- Header & navigation ------------------------------------------------
    enable_header_logo = models.BooleanField(
        default=True,
        help_text="Show the uploaded header logo. The site name is used when no logo is uploaded.",
    )
    header_logo = models.ImageField(upload_to="navigation/", blank=True)
    header_logo_alt = models.CharField(
        max_length=160,
        blank=True,
        help_text="Describe the uploaded logo for people who cannot see it.",
    )
    enable_megamenu = models.BooleanField(
        default=True,
        help_text="Use the grouped megamenu. When off, the compact default navigation is shown.",
    )
    navigation_menu_label = models.CharField(max_length=40, default="Menu")
    enable_accessibility_panel = models.BooleanField(
        default=True,
        help_text="Show the accessibility button in the header. It opens display options: dark mode, contrast, text size, reduced motion, print.",
    )

    # --- Announcement ----------------------------------------------------------
    enable_announcement = models.BooleanField(default=False)
    announcement_text = models.CharField(
        max_length=200,
        blank=True,
        help_text="Short banner text shown above the header while enabled.",
    )
    announcement_url = models.CharField(
        max_length=300, blank=True, help_text="Optional link target for the announcement banner."
    )

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
    enable_articles = models.BooleanField(
        default=True,
        help_text="Publishes article index and detail pages and exposes their links.",
    )
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

    # --- Footer ---------------------------------------------------------------
    enable_footer = models.BooleanField(default=True)
    footer_note = models.CharField(
        max_length=240,
        blank=True,
        default="A production-shaped Django skeleton. Change the site from the control panel.",
    )
    footer_bottom_left = models.CharField(
        max_length=180,
        blank=True,
        default="All public content is controlled from the admin.",
    )
    footer_bottom_right = models.CharField(
        max_length=180,
        blank=True,
        default="Django 5.2 · zero build step · output minified",
    )
    starter_content_seeded = models.BooleanField(default=False, editable=False)

    # --- Forms & anti-spam ------------------------------------------------------
    enable_contact_form = models.BooleanField(default=True)
    enable_message_auto_delete = models.BooleanField(
        default=True,
        help_text="Data minimisation: stored contact messages are deleted automatically after the retention window.",
    )
    message_retention_days = models.PositiveIntegerField(default=30)
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
    enable_email_otp = models.BooleanField(
        default=False,
        help_text="Registration requires entering a one-time code sent by email before the account becomes active.",
    )
    registration_requires_approval = models.BooleanField(
        default=False,
        help_text="New users are created inactive; an admin activates them in People.",
    )

    # --- Embeds -------------------------------------------------------------------
    enable_calcom_embed = models.BooleanField(default=False)
    calcom_link = models.CharField(max_length=200, blank=True)
    enable_stripe_buy_button = models.BooleanField(
        default=False,
        help_text="Master switch. Buy buttons come from the Stripe buttons table; the publishable key below is shared.",
    )
    stripe_publishable_key = models.CharField(max_length=128, blank=True)

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
        default=True, help_text="Show the leave-site confirmation modal for outbound clicks."
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

    def clean(self):
        if self.header_logo and not self.header_logo_alt.strip():
            raise ValidationError({"header_logo_alt": "Describe the uploaded logo."})

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


class EmailCode(models.Model):
    """Short-lived one-time email confirmation code (registration)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="email_codes", on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=64)
    purpose = models.CharField(max_length=30, default="registration")
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField()

    class Meta:
        ordering = ["-created"]

    def __str__(self) -> str:
        return f"code for {self.user_id} ({self.purpose})"


class Article(models.Model):
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    category = models.CharField(max_length=80, default="cybersecurity")
    content = models.TextField(help_text="Plain text. Blank lines become paragraphs.")
    meta_description = models.CharField(max_length=160)
    meta_keywords = models.CharField(
        max_length=300,
        blank=True,
        help_text="Optional comma-separated search terms.",
    )
    excerpt = models.CharField(max_length=320)
    author_name = models.CharField(max_length=120, default="Editorial team")
    hero_image = models.ImageField(upload_to="articles/hero/", blank=True)
    hero_image_alt = models.CharField(max_length=200, blank=True)
    hero_image_caption = models.CharField(max_length=240, blank=True)
    hero_image_credit = models.CharField(max_length=160, blank=True)
    og_image = models.ImageField(upload_to="articles/og/", blank=True)
    seo_title = models.CharField(max_length=110, blank=True)
    show_disclaimer = models.BooleanField(default=False)
    show_ai_disclosure = models.BooleanField(default=False)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_featured", "-published_at", "-pk"]

    def __str__(self) -> str:
        return self.title

    def clean(self):
        if self.hero_image and not self.hero_image_alt.strip():
            raise ValidationError({"hero_image_alt": "Describe the hero image for people who cannot see it."})

    def get_absolute_url(self):
        return reverse("article_detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from core.mediatools import auto_webp

        for field_name in ("hero_image", "og_image"):
            auto_webp(self, field_name)


class ArticleImage(models.Model):
    article = models.ForeignKey(Article, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="articles/content/")
    alt_text = models.CharField(max_length=200)
    caption = models.CharField(max_length=240, blank=True)
    credit = models.CharField(max_length=160, blank=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "pk"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from core.mediatools import auto_webp

        auto_webp(self, "image")

    def __str__(self) -> str:
        return self.alt_text


class ArticleBlock(models.Model):
    """Ordered content element inside an article. Drag to reorder in the
    admin; the preview renders the current editor state."""

    KIND_HEADING = "heading"
    KIND_TEXT = "text"
    KIND_QUOTE = "quote"
    KIND_IMAGE = "image"
    KIND_VIDEO = "video"
    KIND_BUY = "buy"
    KIND_DIVIDER = "divider"
    KIND_CHOICES = (
        (KIND_HEADING, "Heading"),
        (KIND_TEXT, "Paragraph"),
        (KIND_QUOTE, "Quote"),
        (KIND_IMAGE, "Image"),
        (KIND_VIDEO, "Video"),
        (KIND_BUY, "Stripe buy button"),
        (KIND_DIVIDER, "Divider"),
    )

    article = models.ForeignKey(Article, related_name="blocks", on_delete=models.CASCADE)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_TEXT)
    heading_level = models.CharField(
        max_length=2, choices=(("2", "H2"), ("3", "H3")), default="2", blank=True,
        help_text="Heading blocks only.",
    )
    text = models.TextField(blank=True, help_text="Heading, paragraph or quote text.")
    quote_attribution = models.CharField(max_length=160, blank=True, help_text="Quote blocks only.")
    image = models.ForeignKey(
        ArticleImage, related_name="blocks", on_delete=models.SET_NULL, blank=True, null=True,
        help_text="Pick one of the images uploaded for this article.",
    )
    video_file = models.FileField(upload_to="articles/videos/", blank=True, help_text="Internal video (mp4, webm).")
    video_url = models.CharField(
        max_length=400, blank=True, help_text="External YouTube or Vimeo URL. Loads only after consent."
    )
    video_caption = models.CharField(max_length=240, blank=True)
    buy_button = models.ForeignKey(
        "StripeButton", related_name="blocks", on_delete=models.SET_NULL, blank=True, null=True
    )
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "pk"]

    def clean(self):
        errors = {}
        if self.kind in (self.KIND_HEADING, self.KIND_TEXT, self.KIND_QUOTE) and not self.text.strip():
            errors["text"] = "This block needs text."
        if self.kind == self.KIND_IMAGE and self.image is None:
            errors["image"] = "Pick an uploaded article image."
        if self.kind == self.KIND_VIDEO and not (self.video_file or self.video_url.strip()):
            errors["video_url"] = "Upload a video file or add an external URL."
        if self.kind == self.KIND_BUY and self.buy_button is None:
            errors["buy_button"] = "Choose a Stripe buy button."
        if errors:
            raise ValidationError(errors)

    @property
    def video_parts(self):
        from core.mediatools import video_embed_parts

        return video_embed_parts(self.video_url)

    @property
    def video_provider(self) -> str:
        return self.video_parts[0]

    @property
    def video_embed_url(self) -> str:
        return self.video_parts[1]

    def __str__(self) -> str:
        label = self.get_kind_display()
        if self.text:
            label += ": " + self.text[:40]
        elif self.image_id:
            label += f": {self.image.alt_text}"
        return label


class StripeButton(models.Model):
    """A reusable Stripe Buy Button. Multiple products, one shared key."""

    label = models.CharField(max_length=120, help_text="Admin-only name, e.g. 'Audit package'.")
    buy_button_id = models.CharField(max_length=128, help_text="From the Stripe Buy Button code: buy-button-id.")
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["sort_order", "pk"]

    def __str__(self) -> str:
        return self.label


class RobotsRule(models.Model):
    ALLOW = "allow"
    DISALLOW = "disallow"
    DIRECTIVE_CHOICES = ((DISALLOW, "Disallow"), (ALLOW, "Allow"))

    path = models.CharField(
        max_length=240,
        help_text="Path or prefix. /static/ covers every URL that starts with /static/.",
    )
    directive = models.CharField(max_length=10, choices=DIRECTIVE_CHOICES, default=DISALLOW)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    note = models.CharField(max_length=160, blank=True, help_text="Admin-only explanation.")

    class Meta:
        ordering = ["sort_order", "path", "pk"]
        constraints = [models.UniqueConstraint(fields=["path", "directive"], name="unique_robots_rule")]

    def clean(self):
        self.path = (self.path or "").strip()
        if not self.path.startswith("/"):
            raise ValidationError({"path": "Start paths with /."})

    def __str__(self) -> str:
        return f"{self.get_directive_display()}: {self.path}"


class NavigationItem(models.Model):
    PAGE_CUSTOM = "custom"
    PAGE_HOME = "home"
    PAGE_DEMO = "demo"
    PAGE_ARTICLES = "articles"
    PAGE_CONTACT = "contact"
    PAGE_ACCOUNT = "account"
    PAGE_LOGIN = "login"
    PAGE_REGISTER = "register"
    PAGE_LOGOUT = "logout"
    PAGE_ADMIN = "admin"
    PAGE_PRIVACY = "privacy"
    PAGE_IMPRINT = "imprint"
    PAGE_ACCESSIBILITY = "accessibility"
    PAGE_CHOICES = (
        (PAGE_CUSTOM, "Custom URL"),
        (PAGE_HOME, "Home"),
        (PAGE_DEMO, "Demo"),
        (PAGE_ARTICLES, "Articles"),
        (PAGE_CONTACT, "Contact"),
        (PAGE_ACCOUNT, "Account"),
        (PAGE_LOGIN, "Sign in"),
        (PAGE_REGISTER, "Register"),
        (PAGE_LOGOUT, "Sign out"),
        (PAGE_ADMIN, "Admin"),
        (PAGE_PRIVACY, "Privacy"),
        (PAGE_IMPRINT, "Imprint"),
        (PAGE_ACCESSIBILITY, "Accessibility"),
    )

    site_configuration = models.ForeignKey(
        SiteConfiguration,
        related_name="navigation_items",
        on_delete=models.CASCADE,
        default=1,
    )
    group = models.CharField(
        max_length=80,
        default="Explore",
        help_text="Items with the same group name form one megamenu column.",
    )
    label = models.CharField(max_length=100)
    description = models.CharField(
        max_length=180,
        blank=True,
        help_text="Optional supporting line shown in the megamenu.",
    )
    page = models.CharField(max_length=20, choices=PAGE_CHOICES, default=PAGE_CUSTOM)
    url = models.CharField(max_length=500, blank=True, help_text="Used only for Custom URL links.")
    sort_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "pk"]

    def clean(self):
        if self.page == self.PAGE_CUSTOM and not self.url.strip():
            raise ValidationError({"url": "Add a URL or choose an automatic page."})

    def __str__(self) -> str:
        return f"{self.group}: {self.label}"


class FooterSection(models.Model):
    title = models.CharField(max_length=80)
    sort_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "pk"]

    def __str__(self) -> str:
        return self.title


class FooterItem(models.Model):
    KIND_LINK = "link"
    KIND_TEXT = "text"
    KIND_MEDIA = "media"
    KIND_ACTION = "action"
    KIND_CHOICES = (
        (KIND_LINK, "Link"),
        (KIND_TEXT, "Text block"),
        (KIND_MEDIA, "Logo or image"),
        (KIND_ACTION, "Site action"),
    )

    PAGE_CUSTOM = "custom"
    PAGE_HOME = "home"
    PAGE_DEMO = "demo"
    PAGE_ARTICLES = "articles"
    PAGE_CONTACT = "contact"
    PAGE_ACCOUNT = "account"
    PAGE_LOGIN = "login"
    PAGE_REGISTER = "register"
    PAGE_ADMIN = "admin"
    PAGE_PRIVACY = "privacy"
    PAGE_IMPRINT = "imprint"
    PAGE_ACCESSIBILITY = "accessibility"
    PAGE_ROBOTS = "robots"
    PAGE_SITEMAP = "sitemap"
    PAGE_LLMS = "llms"
    PAGE_LLMS_FULL = "llms_full"
    PAGE_SECURITY = "security"
    PAGE_HUMANS = "humans"
    PAGE_CHOICES = (
        (PAGE_CUSTOM, "Custom URL"),
        (PAGE_HOME, "Home"),
        (PAGE_DEMO, "Demo"),
        (PAGE_ARTICLES, "Articles"),
        (PAGE_CONTACT, "Contact"),
        (PAGE_ACCOUNT, "Account"),
        (PAGE_LOGIN, "Sign in"),
        (PAGE_REGISTER, "Register"),
        (PAGE_ADMIN, "Admin"),
        (PAGE_PRIVACY, "Privacy"),
        (PAGE_IMPRINT, "Imprint"),
        (PAGE_ACCESSIBILITY, "Accessibility"),
        (PAGE_ROBOTS, "robots.txt"),
        (PAGE_SITEMAP, "sitemap.xml"),
        (PAGE_LLMS, "llms.txt"),
        (PAGE_LLMS_FULL, "llms-full.txt"),
        (PAGE_SECURITY, "security.txt"),
        (PAGE_HUMANS, "humans.txt"),
    )

    ACTION_COOKIE = "cookie"
    ACTION_DARK = "dark"
    ACTION_TEXT = "text_size"
    ACTION_MOTION = "motion"
    ACTION_PRINT = "print"
    ACTION_LOGOUT = "logout"
    ACTION_CHOICES = (
        (ACTION_COOKIE, "Open cookie settings"),
        (ACTION_DARK, "Toggle dark mode"),
        (ACTION_TEXT, "Change text size"),
        (ACTION_MOTION, "Toggle reduced motion"),
        (ACTION_PRINT, "Print page"),
        (ACTION_LOGOUT, "Sign out"),
    )

    section = models.ForeignKey(FooterSection, related_name="items", on_delete=models.CASCADE)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default=KIND_LINK)
    label = models.CharField(max_length=100, blank=True)
    page = models.CharField(max_length=20, choices=PAGE_CHOICES, default=PAGE_CUSTOM, blank=True)
    url = models.CharField(max_length=500, blank=True, help_text="Used only for Custom URL links.")
    text = models.TextField(blank=True, help_text="Used only for Text block entries.")
    media = models.FileField(upload_to="footer/", blank=True)
    media_alt = models.CharField(max_length=160, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, blank=True)
    sort_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)
    quiet = models.BooleanField(
        default=False,
        help_text="Positions this entry as a low-contrast footer credit.",
    )

    class Meta:
        ordering = ["sort_order", "pk"]

    def clean(self):
        errors = {}
        if self.kind == self.KIND_LINK and self.page == self.PAGE_CUSTOM and not self.url.strip():
            errors["url"] = "Add a URL or choose an automatic page."
        if self.kind == self.KIND_TEXT and not self.text.strip():
            errors["text"] = "Add text for this entry."
        if self.kind == self.KIND_MEDIA and not self.media:
            errors["media"] = "Upload a logo or image."
        if self.kind == self.KIND_ACTION and not self.action:
            errors["action"] = "Choose the action this entry runs."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return self.label or self.get_kind_display()
