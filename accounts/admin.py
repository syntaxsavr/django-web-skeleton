"""Admin for the accounts app. The user admin gets the privacy controls:
one-way hashed-email conversion, disabling, immediate pseudonymisation."""

import hashlib

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from core.admin_mixins import DescribedAdminMixin

from accounts.models import (
    ConsentText,
    DataExportRequest,
    LoginEvent,
    RegistrationField,
    UserConsent,
    UserProfile,
)

User = get_user_model()

# unfold registers its own UserAdmin; swap it for ours so the privacy
# controls replace the stock one instead of colliding.
from django.contrib.admin import site as admin_site

if User in admin_site._registry:
    admin_site.unregister(User)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Privacy and profile"
    fields = ("mailhashed", "email_hash", "is_anonymous", "avatar", "extra_data",
              "data_deletion_requested", "data_deletion_at", "account_deletion_at")
    readonly_fields = ("email_hash", "data_deletion_requested", "data_deletion_at", "account_deletion_at")


@admin.register(User)
class SkeletonUserAdmin(DjangoUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ("username", "email", "mailhashed", "is_anonymous", "is_staff", "is_active")
    list_filter = DjangoUserAdmin.list_filter + ("profile__mailhashed", "profile__is_anonymous")
    actions = ("convert_to_hashed", "disable_accounts", "pseudonymise_now")

    @admin.display(boolean=True, description="Mail hashed")
    def mailhashed(self, obj):
        return getattr(getattr(obj, "profile", None), "mailhashed", False)

    @admin.display(boolean=True, description="Anonymous")
    def is_anonymous(self, obj):
        return getattr(getattr(obj, "profile", None), "is_anonymous", False)

    @admin.action(description="Convert to hashed-email account (ONE-WAY)")
    def convert_to_hashed(self, request, queryset):
        converted = 0
        for user in queryset:
            if not user.email:
                continue
            profile = UserProfile.for_user(user)
            if profile.mailhashed:
                continue
            profile.mailhashed = True
            profile.email_hash = hashlib.sha256(user.email.strip().lower().encode()).hexdigest()
            user.email = f"hashed-{profile.email_hash[:12]}@invalid"
            user.save(update_fields=["email"])
            profile.save(update_fields=["mailhashed", "email_hash", "updated"])
            converted += 1
        messages.warning(
            request,
            f"{converted} account(s) converted. This is one-way: the plain email is gone from the "
            "database and login matches the hash. Only a manual edit or deletion changes it.",
        )

    @admin.action(description="Disable selected accounts")
    def disable_accounts(self, request, queryset):
        updated = queryset.update(is_active=False)
        messages.info(request, f"{updated} account(s) disabled.")

    @admin.action(description="Pseudonymise now (GDPR erase, keeps row)")
    def pseudonymise_now(self, request, queryset):
        from accounts.maintenance import _pseudonymise_user

        for user in queryset:
            profile = UserProfile.for_user(user)
            profile.account_deletion_at = None
            profile.save(update_fields=["account_deletion_at", "updated"])
            user.consents.all().delete()
            user.login_events.all().delete()
            user.export_requests.all().delete()
            _pseudonymise_user(user)
        messages.warning(request, "Selected rows pseudonymised. Data removed, identifiers scrambled.")


@admin.register(RegistrationField)
class RegistrationFieldAdmin(DescribedAdminMixin, admin.ModelAdmin):
    changelist_description = (
        "Fields of the signup form (and the profile-completion page). Every active row is one form field; "
        "required fields force existing users to fill them in at their next visit. Values are sanitized, stored "
        "on the user profile and included in the GDPR data export."
    )
    list_display = ("label", "slug", "kind", "required", "active", "sort_order")
    list_editable = ("required", "active", "sort_order")
    prepopulated_fields = {"slug": ("label",)}
    ordering = ("sort_order", "pk")


@admin.register(ConsentText)
class ConsentTextAdmin(DescribedAdminMixin, admin.ModelAdmin):
    changelist_description = (
        "Consent checkboxes shown on the signup form. They are NEVER pre-ticked (GDPR): a user must actively tick them. "
        "What each user accepted is snapshotted under 'User consent acceptances'. Editing text here does not change past acceptances - bump the version."
    )
    list_display = ("title", "slug", "required", "active", "version", "sort_order")
    list_editable = ("required", "active", "version", "sort_order")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("sort_order", "pk")

    def save_model(self, request, obj, form, change):
        from core.sanitizers import clean_multiline

        obj.body = clean_multiline(obj.body)
        super().save_model(request, obj, form, change)


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ("user", "method", "ip_address", "created")
    list_filter = ("method",)
    date_hierarchy = "created"
    search_fields = ("user__username", "ip_address")
    readonly_fields = ("user", "method", "ip_address", "user_agent", "created")

    def has_add_permission(self, request):
        return False


@admin.register(DataExportRequest)
class DataExportRequestAdmin(DescribedAdminMixin, admin.ModelAdmin):
    changelist_description = (
        "GDPR data-export requests. Users wait out the configured waiting period, then download a gzipped archive of "
        "everything the site stores about them. Archives auto-delete after the export retention window; the files live in "
        "PRIVATE storage and are only reachable through the authenticated download view."
    )
    list_display = ("user", "status", "created", "ready_at", "expires_at")
    list_filter = ("status",)
    readonly_fields = ("user", "status", "created", "ready_at", "expires_at", "file")

    def has_add_permission(self, request):
        return False


admin.site.register(UserConsent)
