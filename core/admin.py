"""Admin wiring. django-unfold provides the skin; the interesting part is
the SiteConfiguration control panel: one row, grouped fieldsets, no add or
delete so the singleton stays a singleton."""

from django.contrib import admin
from django.core.cache import cache

from core.admin_mixins import DescribedAdminMixin
from core.middleware import ProtectedPageMiddleware
from core.models import (
    Article,
    ArticleBlock,
    ArticleImage,
    ContactMessage,
    FooterItem,
    FooterSection,
    NavigationItem,
    ProtectedPage,
    OpsLog,
    RobotsRule,
    SiteConfiguration,
    StripeButton,
)


class NavigationItemInline(admin.TabularInline):
    model = NavigationItem
    extra = 1
    fields = ("sort_order", "active", "group", "label", "description", "page", "url")


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    inlines = (NavigationItemInline,)
    fieldsets = (
        # ------------------------------------------------------------------
        # 1) THE SWITCH MAP: every on/off in one place, no keys, no texts.
        # ------------------------------------------------------------------
        (
            "1 · Feature switches",
            {
                "description": "The main on/off map of the site. Turn features off and they disappear everywhere: routes, navigation, footer, sitemap, AI files. Fine-tuning for each lives in the collapsed groups below.",
                "fields": (
                    "enable_announcement",
                    "enable_header_logo",
                    "enable_megamenu",
                    "enable_accessibility_panel",
                    "enable_footer",
                    "enable_articles",
                    "enable_contact_form",
                    "enable_cookie_consent",
                    "allow_avatar_upload",
                    "enable_webp_conversion",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "2 · Accounts & signup switches",
            {
                "description": "enable_accounts off removes every trace of accounts (login, register, account pages 404, links vanish). Enable the login methods you want - code and magic-link logins never reveal whether an address exists. With force 2FA on, every account (you included) must confirm a second factor before protected areas open.",
                "fields": (
                    "enable_accounts",
                    "enable_login_password",
                    "enable_login_email_otp",
                    "enable_login_magic_link",
                    "enable_login_anonymous",
                    "enable_public_registration",
                    "enable_email_otp",
                    "registration_requires_approval",
                    "force_2fa_users",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "3 · SEO switches",
            {
                "description": "Search-engine surfaces. Off = the route stops answering and the page drops out of sitemap, robots.txt references and llms.txt. The noindex kill switch is for staging: every page answers with noindex.",
                "fields": (
                    "enable_sitemap",
                    "enable_robots_txt",
                    "enable_llms_txt",
                    "enable_jsonld",
                    "enable_indexnow",
                    "robots_noindex_whole_site",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "4 · Protection & privacy switches",
            {
                "description": "Each toggle is one middleware behaviour: scraper blocking on legal pages, the Content-Security-Policy, the outbound-link snatcher (tagging + optional UTM and leave-site modal), message auto-deletion and the Turnstile challenge. Turning one off disables that layer only.",
                "fields": (
                    "enable_scraper_block",
                    "enable_csp",
                    "enable_external_link_handling",
                    "external_link_utm",
                    "external_link_modal",
                    "enable_message_auto_delete",
                    "enable_turnstile",
                    "enable_calcom_embed",
                    "enable_stripe_buy_button",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "5 · Tracking switch",
            {
                "description": "Master switch for ALL measurement. Even when on, a tracker only loads after visitor consent AND when its ID is filled in below (collapsed group 'Tracking IDs').",
                "fields": ("enable_tracking",),
            },
        ),
        # ------------------------------------------------------------------
        # 2) DETAILS: keys, texts and numbers. Collapsed so the switch map
        #    stays the first thing you see.
        # ------------------------------------------------------------------
        (
            "Site identity (rebranding)",
            {
                "description": "Canonical origin drives canonical URLs, hreflang, JSON-LD, sitemap and IndexNow - no trailing slash. Set this correctly before going live.",
                "fields": ("site_name", "canonical_origin", "contact_email", "default_meta_description", "theme_color"),
                "classes": ("collapse",),
            },
        ),
        (
            "Header & navigation details",
            {
                "description": "Logo upload (fallback is the site name), megamenu label and the accessibility button switch. Megamenu LINKS live in their own admin section (Navigation items).",
                "fields": ("header_logo", "header_logo_alt", "navigation_menu_label"),
                "classes": ("collapse",),
            },
        ),
        (
            "Announcement text",
            {
                "description": "The banner above the header. Only shown while the announcement switch (group 1) is on.",
                "fields": ("announcement_text", "announcement_url"),
                "classes": ("collapse",),
            },
        ),
        (
            "Footer text",
            {
                "description": "Brand column text and the bottom bar strings. Footer COLUMNS and LINKS are separate rows under Footer sections.",
                "fields": ("footer_note", "footer_bottom_left", "footer_bottom_right"),
                "classes": ("collapse",),
            },
        ),
        (
            "Tracking IDs",
            {
                "description": "One row per tracker. Paste the ID and the tracker is declared to the consent manager - empty ID means the tracker does not exist for the consent system at all.",
                "fields": (
                    "consent_cookie_name",
                    "google_tag_manager_id",
                    "google_analytics_measurement_id",
                    "google_ads_id",
                    "google_ads_conversion_label",
                    "meta_pixel_id",
                    "linkedin_partner_id",
                    "microsoft_ads_uet_tag_id",
                    "microsoft_clarity_project_id",
                    "hotjar_site_id",
                    "tiktok_pixel_id",
                    "pinterest_tag_id",
                    "x_twitter_pixel_id",
                    "matomo_url",
                    "matomo_site_id",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "SEO keys",
            {
                "description": "Search-engine verification tokens render as meta tags when filled. The IndexNow key is served at /<key>.txt as proof and used by manage.py indexnow.",
                "fields": (
                    "indexnow_key",
                    "google_site_verification",
                    "bing_site_verification",
                    "facebook_domain_verification",
                    "pinterest_domain_verification",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Turnstile & anti-spam details",
            {
                "description": "Cloudflare keys for the contact-form challenge (fail closed when enabled without a secret). Honeypot and time-trap run additionally; the cooldown is per session.",
                "fields": ("turnstile_site_key", "turnstile_secret_key", "enable_honeypot", "form_min_seconds", "contact_rate_limit_seconds"),
                "classes": ("collapse",),
            },
        ),
        (
            "Login details",
            {
                "description": "Which identifier the password login accepts, and the length of generated anonymous access codes.",
                "fields": ("login_identifier_mode", "anonymous_token_length"),
                "classes": ("collapse",),
            },
        ),
        (
            "Embed keys",
            {
                "description": "Cal.com booking link and the shared Stripe publishable key. Individual products live under Stripe buttons.",
                "fields": ("calcom_link", "stripe_publishable_key"),
                "classes": ("collapse",),
            },
        ),
        (
            "Retention & exports (GDPR)",
            {
                "description": "How long data is kept, with deliberate friction: contact messages and login traces auto-delete after their windows; exports wait out a waiting period, stay downloadable for their retention, then a cooldown applies before the next request; deletions execute after the delay and suspend the account until then.",
                "fields": (
                    "message_retention_days",
                    "login_event_retention_days",
                    "export_wait_minutes",
                    "export_retention_days",
                    "export_cooldown_days",
                    "deletion_delay_hours",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Media details",
            {
                "description": "WebP conversion quality for article images and the avatar upload size cap.",
                "fields": ("webp_quality", "avatar_max_kb"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete("core:site_configuration:solo")
        ProtectedPageMiddleware.invalidate_cache()

    class Media:
        js = ("core/js/admin-image-drop.js",)


@admin.register(ProtectedPage)
class ProtectedPageAdmin(DescribedAdminMixin, admin.ModelAdmin):
    changelist_description = (
        "Login-wall rules: every active row puts a path (or everything below a prefix) behind login. "
        "Anonymous visitors are redirected to the sign-in page. Use this for member areas, reports, downloads - "
        "anything that should not be public. Changes apply immediately."
    )
    list_display = ("path", "match_type", "title", "active")
    list_filter = ("active", "match_type")
    search_fields = ("path", "title")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        ProtectedPageMiddleware.invalidate_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        ProtectedPageMiddleware.invalidate_cache()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["path"].help_text = "No leading domain. Prefix match covers everything below the path."
        return form


@admin.register(ContactMessage)
class ContactMessageAdmin(DescribedAdminMixin, admin.ModelAdmin):
    changelist_description = (
        "Inbound messages from the contact form. Data minimisation: they are DELETED automatically after the retention "
        "window in Site configuration (Data minimisation) - do not use this list as a long-term archive; move anything "
        "worth keeping into your CRM. 'Responded' is your personal to-do flag."
    )
    list_display = ("created", "name", "email", "preference", "responded")
    list_filter = ("preference", "responded")
    search_fields = ("name", "email", "message")
    readonly_fields = ("created", "name", "email", "phone", "preference", "message")
    list_editable = ("responded",)

    def has_add_permission(self, request):
        return False


class ArticleImageInline(admin.StackedInline):
    model = ArticleImage
    extra = 1
    fields = ("image", "alt_text", "caption", "credit", "sort_order")


class ArticleBlockInline(admin.StackedInline):
    model = ArticleBlock
    extra = 1
    classes = ("article-blocks",)
    fieldsets = (
        (None, {"fields": ("kind", "sort_order")}),
        ("Content", {"fields": ("text", "heading_level", "quote_attribution")}),
        ("Media", {"fields": ("image", "video_file", "video_url", "video_caption")}),
        ("Commerce", {"fields": ("buy_button",)}),
    )


@admin.register(StripeButton)
class StripeButtonAdmin(DescribedAdminMixin, admin.ModelAdmin):
    changelist_description = (
        "Reusable Stripe Buy Buttons. Create one row per product (the buy-button-id comes from Stripe's Buy Button "
        "code), then attach it to any article as a 'Stripe buy button' block. Buttons render only when the master "
        "switch is on AND the visitor consents to the Stripe service."
    )
    list_display = ("label", "buy_button_id", "active", "sort_order")
    list_editable = ("active", "sort_order")
    ordering = ("sort_order", "pk")


@admin.register(Article)
class ArticleAdmin(DescribedAdminMixin, admin.ModelAdmin):
    changelist_description = (
        "Editorial content. Build articles from blocks (heading, text, quote, image, video, buy button, divider) - "
        "the Preview button renders your current editor state without saving. Untick 'Published' to hide an article "
        "everywhere without deleting it."
    )
    list_display = ("title", "category", "author_name", "published_at", "is_featured", "published")
    list_filter = ("published", "is_featured", "show_disclaimer", "show_ai_disclosure", "category")
    search_fields = ("title", "excerpt", "content", "meta_keywords")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_featured", "published")
    date_hierarchy = "published_at"
    inlines = (ArticleImageInline, ArticleBlockInline)
    fieldsets = (
        ("Article", {"fields": ("title", "slug", "category", "author_name", "excerpt", "content")}),
        ("Lead image", {"fields": ("hero_image", "hero_image_alt", "hero_image_caption", "hero_image_credit")}),
        ("Search and sharing", {"fields": ("seo_title", "meta_description", "meta_keywords", "og_image")}),
        (
            "Publishing",
            {"fields": ("published", "is_featured", "published_at", "show_disclaimer", "show_ai_disclosure")},
        ),
    )

    class Media:
        js = ("core/js/admin-image-drop.js", "core/js/admin/article-editor.js")


@admin.register(RobotsRule)
class RobotsRuleAdmin(DescribedAdminMixin, admin.ModelAdmin):
    changelist_description = (
        "Rules for robots.txt: search engines are told which paths to skip. A path covers everything below it. "
        "This is advisory only - well-behaved crawlers obey, so keep truly private material behind the login wall instead."
    )
    list_display = ("path", "directive", "active", "sort_order", "note")
    list_editable = ("directive", "active", "sort_order")
    list_filter = ("active", "directive")
    search_fields = ("path", "note")
    ordering = ("sort_order", "path")


class FooterItemInline(admin.TabularInline):
    model = FooterItem
    extra = 1
    fields = (
        "sort_order",
        "active",
        "quiet",
        "kind",
        "label",
        "page",
        "url",
        "text",
        "media",
        "media_alt",
        "action",
    )


@admin.register(FooterSection)
class FooterSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "sort_order", "active")
    list_editable = ("sort_order", "active")
    ordering = ("sort_order",)
    inlines = (FooterItemInline,)

    class Media:
        js = ("core/js/admin-image-drop.js",)


@admin.register(OpsLog)
class OpsLogAdmin(admin.ModelAdmin):
    list_display = ("processed_at", "status", "file_name", "author", "purpose")
    list_filter = ("status",)
    readonly_fields = ("file_name", "status", "author", "purpose", "created_at", "detail", "processed_at")
    ordering = ("-processed_at",)

    def has_add_permission(self, request):
        return False


def badge_contact_messages(request):
    return ContactMessage.objects.count()


def badge_config_changed(request):
    config = SiteConfiguration.get_solo()
    return "" if config.starter_content_seeded else "!"


admin.site.site_header = "Skeleton control panel"
admin.site.site_title = "Skeleton admin"
admin.site.index_title = "Configuration"
