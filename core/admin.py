"""Admin wiring. django-unfold provides the skin; the interesting part is
the SiteConfiguration control panel: one row, grouped fieldsets, no add or
delete so the singleton stays a singleton."""

from django.contrib import admin
from django.core.cache import cache

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
        (
            "Site identity",
            {
                "fields": (
                    "site_name",
                    "canonical_origin",
                    "contact_email",
                    "default_meta_description",
                    "theme_color",
                )
            },
        ),
        (
            "Header & navigation",
            {
                "description": "Upload the brand mark and edit ordered megamenu links below. Reuse a group name to place links in the same column.",
                "fields": (
                    "enable_header_logo",
                    "header_logo",
                    "header_logo_alt",
                    "enable_megamenu",
                    "navigation_menu_label",
                    "enable_accessibility_panel",
                ),
            },
        ),
        (
            "Announcement",
            {
                "fields": (
                    "enable_announcement",
                    "announcement_text",
                    "announcement_url",
                )
            },
        ),
        (
            "Consent & tracking",
            {
                "fields": (
                    "enable_cookie_consent",
                    "consent_cookie_name",
                    "enable_tracking",
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
                )
            },
        ),
        (
            "SEO",
            {
                "fields": (
                    "enable_articles",
                    "enable_sitemap",
                    "enable_robots_txt",
                    "enable_llms_txt",
                    "enable_jsonld",
                    "enable_indexnow",
                    "indexnow_key",
                    "google_site_verification",
                    "bing_site_verification",
                    "facebook_domain_verification",
                    "pinterest_domain_verification",
                    "robots_noindex_whole_site",
                )
            },
        ),
        (
            "Footer",
            {
                "description": "Footer columns and entries are edited under Footer sections. Do not edit the public template.",
                "fields": (
                    "enable_footer",
                    "footer_note",
                    "footer_bottom_left",
                    "footer_bottom_right",
                ),
            },
        ),
        (
            "Forms & anti-spam",
            {
                "fields": (
                    "enable_contact_form",
                    "enable_turnstile",
                    "turnstile_site_key",
                    "turnstile_secret_key",
                    "enable_honeypot",
                    "form_min_seconds",
                    "contact_rate_limit_seconds",
                )
            },
        ),
        (
            "Auth",
            {
                "fields": (
                    "enable_public_registration",
                    "enable_email_otp",
                    "registration_requires_approval",
                )
            },
        ),
        (
            "Embeds",
            {
                "fields": (
                    "enable_calcom_embed",
                    "calcom_link",
                    "enable_stripe_buy_button",
                    "stripe_publishable_key",
                )
            },
        ),
        (
            "Data minimisation",
            {
                "fields": (
                    "enable_message_auto_delete",
                    "message_retention_days",
                )
            },
        ),
        (
            "Middleware switches",
            {
                "fields": (
                    "enable_scraper_block",
                    "enable_csp",
                    "enable_external_link_handling",
                    "external_link_utm",
                    "external_link_modal",
                )
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
class ProtectedPageAdmin(admin.ModelAdmin):
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
class ContactMessageAdmin(admin.ModelAdmin):
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
class StripeButtonAdmin(admin.ModelAdmin):
    list_display = ("label", "buy_button_id", "active", "sort_order")
    list_editable = ("active", "sort_order")
    ordering = ("sort_order", "pk")


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
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
class RobotsRuleAdmin(admin.ModelAdmin):
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


def badge_contact_messages(request):
    return ContactMessage.objects.count()


def badge_config_changed(request):
    config = SiteConfiguration.get_solo()
    return "" if config.starter_content_seeded else "!"


admin.site.site_header = "Skeleton control panel"
admin.site.site_title = "Skeleton admin"
admin.site.index_title = "Configuration"
