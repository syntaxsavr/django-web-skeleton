"""Admin wiring. django-unfold provides the skin.

The control panel is ONE SiteConfiguration row (pk=1) presented as several
focused settings pages through the proxy models in core/models.py: one page
per domain, its master switch always at the top, details collapsed below.
Add/delete stay disabled everywhere so the singleton stays a singleton.
"""

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import StackedInline as UnfoldStackedInline
from unfold.admin import TabularInline as UnfoldTabularInline

from core.admin_mixins import DescribedAdminMixin
from core.middleware import ProtectedPageMiddleware
from core.models import (
    AccountsSettings,
    Article,
    ArticleBlock,
    ArticleImage,
    ArticlesSettings,
    CalcomSettings,
    ContactFormSettings,
    ContactMessage,
    FooterItem,
    FooterSection,
    FooterSettings,
    GeneralSettings,
    HeaderSettings,
    NavigationItem,
    OpsLog,
    ProtectedPage,
    ProtectionSettings,
    RetentionSettings,
    RobotsRule,
    SeoSettings,
    SiteConfiguration,
    StripeButton,
    StripeSettings,
    TrackingSettings,
    TurnstileSettings,
)


class SettingsPageAdmin(UnfoldModelAdmin):
    """Base admin for every settings page: a focused window onto the one
    SiteConfiguration row. There is no changelist to browse - visiting it
    redirects straight to the row's change form."""

    change_form_before_template = "admin/change_form_description.html"
    change_form_description = ""

    def get_queryset(self, request):
        return super().get_queryset(request).filter(pk=1)

    def get_object(self, request, object_id, from_field=None):
        if str(object_id) != "1":
            return None
        return self.model.objects.get_or_create(pk=1)[0]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        config, _created = self.model.objects.get_or_create(pk=1)
        return HttpResponseRedirect(
            reverse(f"admin:core_{self.model._meta.model_name}_change", args=(config.pk,))
        )


@admin.register(GeneralSettings)
class GeneralSettingsAdmin(SettingsPageAdmin):
    changelist_description = ""
    change_form_description = (
        "The identity of the site. The canonical origin (no trailing slash) drives canonical "
        "URLs, hreflang, JSON-LD, the sitemap and IndexNow - set it correctly before going live."
    )
    fieldsets = (
        (
            "Identity",
            {
                "description": "The name is shown in the header when no logo is uploaded, and in machine files (llms.txt, security.txt).",
                "fields": ("site_name", "canonical_origin"),
                "classes": ("wide",),
            },
        ),
        (
            "Contact & metadata",
            {
                "description": "The contact email powers the contact form replies and security.txt. The default meta description is used on pages without their own.",
                "fields": ("contact_email", "default_meta_description", "theme_color"),
                "classes": ("wide",),
            },
        ),
    )


@admin.register(HeaderSettings)
class HeaderSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "Everything above the page content. Flip the switches first; the details sit underneath. "
        "Megamenu LINKS are separate rows: see Navigation items under Content. The announcement "
        "banner stays hidden while its switch is off or its text is empty."
    )
    fieldsets = (
        (
            "Switches",
            {
                "description": "One switch per header feature. Logo off falls back to the site name; megamenu off shows the compact default navigation.",
                "fields": ("enable_header_logo", "enable_megamenu", "enable_accessibility_panel", "enable_announcement"),
                "classes": ("wide",),
            },
        ),
        (
            "Logo & labels",
            {
                "description": "Without an uploaded logo the site name is shown. The alt text is required with a logo.",
                "fields": ("header_logo", "header_logo_alt", "navigation_menu_label"),
                "classes": ("wide",),
            },
        ),
        (
            "Announcement banner text",
            {
                "description": "Short banner above the header. Rendered only while the announcement switch is on and text is set.",
                "fields": ("announcement_text", "announcement_url"),
                "classes": ("wide",),
            },
        ),
    )

    class Media:
        js = ("core/js/admin-image-drop.js",)


@admin.register(FooterSettings)
class FooterSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "The page footer. Switch it off and it disappears everywhere. Columns and links are "
        "separate rows: see Footer sections under Content."
    )
    fieldsets = (
        ("Switch", {"fields": ("enable_footer",), "classes": ("wide",)}),
        (
            "Footer texts",
            {
                "description": "Brand column text and the two bottom-bar strings.",
                "fields": ("footer_note", "footer_bottom_left", "footer_bottom_right"),
                "classes": ("wide",),
            },
        ),
    )


@admin.register(ArticlesSettings)
class ArticlesSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "Master switch for the editorial section. Off: article pages answer 404 and article links "
        "vanish from navigation, footer, sitemap and llms.txt. WebP conversion applies to newly "
        "uploaded article images only; existing files are left as they are."
    )
    fieldsets = (
        ("Switch", {"fields": ("enable_articles",), "classes": ("wide",)}),
        (
            "Article images",
            {
                "description": "Automatic WebP conversion for uploaded article images, and its quality (higher = better, larger).",
                "fields": ("enable_webp_conversion", "webp_quality"),
                "classes": ("wide",),
            },
        ),
    )


@admin.register(SeoSettings)
class SeoSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "Search-engine surfaces. Off = the route stops answering and the page drops out of "
        "sitemap, robots.txt references and llms.txt. The noindex kill switch is for staging: "
        "every page answers with X-Robots-Tag noindex until you turn it off again."
    )
    fieldsets = (
        (
            "Switches",
            {
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
            "Keys & verification",
            {
                "description": "Verification tokens render as meta tags when filled. The IndexNow key is served at /<key>.txt as proof and used by manage.py indexnow.",
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
    )


@admin.register(TrackingSettings)
class TrackingSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "Master switch for ALL measurement. Even when tracking is on, a tracker loads only after "
        "the visitor consents AND its ID is filled in below - an empty ID means the tracker does "
        "not exist for the consent system at all. Consent manager off removes the banner and the gate."
    )
    fieldsets = (
        (
            "Switches",
            {
                "fields": ("enable_tracking", "enable_cookie_consent", "consent_cookie_name"),
                "classes": ("wide",),
            },
        ),
        (
            "Tracker IDs",
            {
                "description": "One row per tracker. Paste the ID and the tracker is declared to the consent manager; leave it empty and it does not exist.",
                "fields": (
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
    )


@admin.register(ContactFormSettings)
class ContactFormSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "The public contact form and its bot defenses. The Cloudflare Turnstile challenge lives on "
        "its own page; how long submitted messages are kept is under Privacy & retention (GDPR)."
    )
    fieldsets = (
        (
            "Switch & defenses",
            {
                "description": "Honeypot and the signed time-trap silently discard bots; the cooldown applies per session. All work without any external service.",
                "fields": ("enable_contact_form", "enable_honeypot", "form_min_seconds", "contact_rate_limit_seconds"),
                "classes": ("wide",),
            },
        ),
    )


@admin.register(TurnstileSettings)
class TurnstileSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "Cloudflare Turnstile on the contact form. Keys from the environment "
        "(TURNSTILE_SITE_KEY / TURNSTILE_SECRET_KEY) always win over the fields below. It fails "
        "closed: enabled without a working secret, the form blocks legitimate submissions too."
    )
    fieldsets = (
        (
            "Switch & keys",
            {"fields": ("enable_turnstile", "turnstile_site_key", "turnstile_secret_key"), "classes": ("wide",)},
        ),
    )


@admin.register(StripeSettings)
class StripeSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "Master switch for commerce. Off: buy buttons never render, even where articles reference "
        "them. On: they render per article and additionally wait for the visitor's Stripe consent. "
        "Products are separate rows: see Stripe buttons under Content."
    )
    fieldsets = (
        (
            "Switch & key",
            {
                "description": "The publishable key is shared by every buy button; it may contain no secret.",
                "fields": ("enable_stripe_buy_button", "stripe_publishable_key"),
                "classes": ("wide",),
            },
        ),
    )


@admin.register(CalcomSettings)
class CalcomSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "Cal.com booking embed. Loads only after the visitor consents to the Cal.com service in "
        "the consent manager."
    )
    fieldsets = (
        ("Switch & link", {"fields": ("enable_calcom_embed", "calcom_link"), "classes": ("wide",)}),
    )


@admin.register(AccountsSettings)
class AccountsSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "Master switch: off removes every trace of accounts - login, registration and account "
        "pages answer 404 and their links vanish. Code and magic-link logins never reveal whether "
        "an address exists. Force 2FA applies to every account, yours included."
    )
    fieldsets = (
        ("Master switch", {"fields": ("enable_accounts",), "classes": ("wide",)}),
        (
            "Login methods",
            {
                "description": "Enable the ways people sign in. Anonymous login means access-code accounts: a random string is the credential, no email, no password.",
                "fields": (
                    "enable_login_password",
                    "enable_login_email_otp",
                    "enable_login_magic_link",
                    "enable_login_anonymous",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "Registration",
            {
                "description": "Email OTP makes registration confirm the address with a one-time code; approval creates new users inactive until an admin activates them.",
                "fields": ("enable_public_registration", "enable_email_otp", "registration_requires_approval"),
                "classes": ("wide",),
            },
        ),
        (
            "Second factor",
            {
                "description": "While on, every account (not only staff) must confirm a second factor before protected areas open.",
                "fields": ("force_2fa_users",),
                "classes": ("wide",),
            },
        ),
        (
            "Details",
            {
                "description": "Which identifier the password login accepts, the length of generated access codes, and avatar uploads.",
                "fields": ("login_identifier_mode", "anonymous_token_length", "allow_avatar_upload", "avatar_max_kb"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(ProtectionSettings)
class ProtectionSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "Each switch is one middleware layer; turning one off disables that layer only. The "
        "scraper block is best-effort deterrence (user agents are client-supplied - not access "
        "control; use the login wall for that), the CSP is skipped on /admin/, and the "
        "outbound-link snatcher tags external anchors."
    )
    fieldsets = (
        (
            "Switches",
            {"fields": ("enable_scraper_block", "enable_csp", "enable_external_link_handling"), "classes": ("wide",)},
        ),
        (
            "Outbound link behaviour",
            {
                "description": "Sub-switches of the outbound-link snatcher: append utm_source=<your host>, and show the leave-site confirmation modal.",
                "fields": ("external_link_utm", "external_link_modal"),
                "classes": ("wide",),
            },
        ),
    )


@admin.register(RetentionSettings)
class RetentionSettingsAdmin(SettingsPageAdmin):
    change_form_description = (
        "How long personal data is kept, with deliberate friction: contact messages and login "
        "traces auto-delete after their windows; data exports wait out a waiting period, stay "
        "downloadable for their retention, then a cooldown applies before the next request; "
        "deletions execute after the delay, suspending the account until then."
    )
    fieldsets = (
        (
            "Contact messages",
            {"fields": ("enable_message_auto_delete", "message_retention_days"), "classes": ("wide",)},
        ),
        ("Login traces", {"fields": ("login_event_retention_days",), "classes": ("wide",)}),
        (
            "Data exports",
            {
                "description": "Wait time between request and download, how long the archive survives, and the minimum days between two requests per user.",
                "fields": ("export_wait_minutes", "export_retention_days", "export_cooldown_days"),
                "classes": ("wide",),
            },
        ),
        (
            "Account deletion",
            {
                "description": "Deletions wait this many hours, during which the account is suspended.",
                "fields": ("deletion_delay_hours",),
                "classes": ("wide",),
            },
        ),
    )


@admin.register(NavigationItem)
class NavigationItemAdmin(DescribedAdminMixin, UnfoldModelAdmin):
    changelist_description = (
        "Megamenu groups and links - one row per entry; rows with the same group name form one "
        "megamenu column. Drag the handle (or edit Sort order) to rearrange, then save. The live "
        "preview on the right shows the saved header. The switches that make entries appear live "
        "in the Configuration section: the megamenu itself in Header & navigation, and "
        "feature-bound destinations in their settings page (Articles, Accounts & login). "
        "A destination whose feature is switched off disappears from the menu automatically."
    )
    changelist_preview_url = "/"
    ordering_field = "sort_order"
    list_display = ("group", "label", "description", "page", "url", "sort_order", "active")
    list_editable = ("sort_order", "active")
    list_filter = ("active", "group")
    search_fields = ("group", "label", "description", "url")
    ordering = ("sort_order", "pk")


@admin.register(ProtectedPage)
class ProtectedPageAdmin(DescribedAdminMixin, UnfoldModelAdmin):
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
class ContactMessageAdmin(DescribedAdminMixin, UnfoldModelAdmin):
    changelist_description = (
        "Inbound messages from the contact form. Data minimisation: they are DELETED automatically after the retention "
        "window in Configuration: Privacy & retention - do not use this list as a long-term archive; move anything "
        "worth keeping into your CRM. 'Responded' is your personal to-do flag."
    )
    list_display = ("created", "name", "email", "preference", "responded")
    list_filter = ("preference", "responded")
    search_fields = ("name", "email", "message")
    readonly_fields = ("created", "name", "email", "phone", "preference", "message")
    list_editable = ("responded",)

    def has_add_permission(self, request):
        return False


class ArticleImageInline(UnfoldStackedInline):
    model = ArticleImage
    extra = 1
    fields = ("image", "alt_text", "caption", "credit", "sort_order")


class ArticleBlockInline(UnfoldStackedInline):
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
class StripeButtonAdmin(DescribedAdminMixin, UnfoldModelAdmin):
    changelist_description = (
        "Reusable Stripe Buy Buttons. Create one row per product (the buy-button-id comes from Stripe's Buy Button "
        "code), then attach it to any article as a 'Stripe buy button' block. Buttons render only when the master "
        "switch (Configuration: Stripe) is on AND the visitor consents to the Stripe service."
    )
    ordering_field = "sort_order"
    list_display = ("label", "buy_button_id", "active", "sort_order")
    list_editable = ("active", "sort_order")
    ordering = ("sort_order", "pk")


@admin.register(Article)
class ArticleAdmin(DescribedAdminMixin, UnfoldModelAdmin):
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
class RobotsRuleAdmin(DescribedAdminMixin, UnfoldModelAdmin):
    changelist_description = (
        "Rules for robots.txt: search engines are told which paths to skip. A path covers everything below it. "
        "This is advisory only - well-behaved crawlers obey, so keep truly private material behind the login wall instead."
    )
    ordering_field = "sort_order"
    list_display = ("path", "directive", "active", "sort_order", "note")
    list_editable = ("directive", "active", "sort_order")
    list_filter = ("active", "directive")
    search_fields = ("path", "note")
    ordering = ("sort_order", "path")


class FooterItemInline(UnfoldTabularInline):
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
class FooterSectionAdmin(DescribedAdminMixin, UnfoldModelAdmin):
    changelist_description = (
        "The footer's columns - add as many as you like, the footer grid grows with them. Each "
        "column holds any mix of links, text blocks, images and action buttons (add them with the "
        "plus on this row). Drag the handle to rearrange columns, then save; the live preview on "
        "the right shows the saved footer as visitors see it. The footer itself switches on and "
        "off in Configuration: Footer."
    )
    changelist_preview_url = "/"
    ordering_field = "sort_order"
    list_display = ("title", "sort_order", "active")
    list_editable = ("sort_order", "active")
    ordering = ("sort_order",)
    inlines = (FooterItemInline,)

    class Media:
        js = ("core/js/admin-image-drop.js",)

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
