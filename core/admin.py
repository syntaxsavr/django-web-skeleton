"""Admin wiring. django-unfold provides the skin; the interesting part is
the SiteConfiguration control panel: one row, grouped fieldsets, no add or
delete so the singleton stays a singleton."""

from django.contrib import admin
from django.core.cache import cache

from core.middleware import ProtectedPageMiddleware
from core.models import ContactMessage, ProtectedPage, SiteConfiguration


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
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
            {"fields": ("enable_public_registration", "registration_requires_approval")},
        ),
        (
            "Embeds",
            {
                "fields": (
                    "enable_calcom_embed",
                    "calcom_link",
                    "enable_stripe_buy_button",
                    "stripe_publishable_key",
                    "stripe_buy_button_id",
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


admin.site.site_header = "Skeleton control panel"
admin.site.site_title = "Skeleton admin"
admin.site.index_title = "Configuration"
