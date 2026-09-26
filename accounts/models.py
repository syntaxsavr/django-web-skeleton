"""User-space models: profiles, consents, login traces, data exports,
registration fields and consent texts.

Everything here is built around two principles:

1. Data minimisation - inbound/user data self-deletes (login events,
   export archives, deleted-account remainders) and the profile stores
   only what the admin actually asked for.
2. Irreversibility where it protects people - `mailhashed` conversion is
   one-way, deletion is scheduled and then executed, identifiers of
   removed accounts are pseudonymised instead of kept.
"""

import hashlib
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from accounts.storage import PrivateMediaStorage
from django.utils import timezone


class UserProfile(models.Model):
    """Per-user privacy and account state. Created lazily on first access."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="profile", on_delete=models.CASCADE
    )
    # One-way anonymisation: once set, the plain email is gone from this
    # account (login matches the hash). Only manual admin edits or deletion
    # can change that; the flag itself must never be switched back.
    mailhashed = models.BooleanField(default=False)
    email_hash = models.CharField(
        max_length=64, blank=True, help_text="sha256 of the lowercased email. Set when mailhashed."
    )
    is_anonymous = models.BooleanField(
        default=False, help_text="Token accounts: no email, no password, token IS the credential."
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    extra_data = models.JSONField(
        default=dict, blank=True, help_text="Values for the admin-defined registration fields."
    )
    # Scheduled data deletion (account stays, non-technical data is purged).
    data_deletion_requested = models.DateTimeField(null=True, blank=True)
    data_deletion_at = models.DateTimeField(null=True, blank=True)
    suspended_by_data_deletion = models.BooleanField(
        default=False,
        help_text="True while the data-deletion flow owns the deactivation. Maintenance only reactivates accounts it deactivated itself.",
    )
    # Scheduled account deletion (row survives pseudonymised).
    account_deletion_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User profile"
        verbose_name_plural = "User profiles"

    def __str__(self) -> str:
        return f"profile:{self.user_id}"

    def clean(self):
        if not self.mailhashed and self.email_hash:
            raise ValidationError({"email_hash": "email_hash belongs to a hashed account."})

    @classmethod
    def for_user(cls, user) -> "UserProfile":
        profile, _created = cls.objects.get_or_create(user=user)
        return profile

    def missing_required_fields(self):
        """Labels of required RegistrationFields without a stored value."""
        data = self.extra_data or {}
        missing = []
        for field in RegistrationField.objects.filter(active=True, required=True).order_by("sort_order", "pk"):
            value = data.get(field.slug, "")
            if value is None or not str(value).strip():
                missing.append(field.label)
        return missing


class ConsentText(models.Model):
    """Admin-managed consent block shown (unticked) at registration.

    Why: consent checkboxes must never be pre-ticked (GDPR). Each active
    row here becomes one checkbox on the signup form. What a user accepted
    is snapshotted into 'user consent acceptances' - editing this text does
    not rewrite past acceptances; bump the version instead."""

    title = models.CharField(
        max_length=160,
        help_text="The checkbox label at registration, e.g. 'I accept the privacy policy'.",
    )
    slug = models.SlugField(
        max_length=80,
        unique=True,
        help_text="Internal key under which acceptances are stored. Never change it after go-live; edit the title instead.",
    )
    body = models.TextField(help_text="Plain text shown under the checkbox.")
    url = models.CharField(max_length=300, blank=True, help_text="Optional link, e.g. the privacy policy.")
    required = models.BooleanField(default=True, help_text="Registration blocks until this box is ticked.")
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    version = models.PositiveSmallIntegerField(
        default=1,
        help_text="Bump this number whenever you edit the text. Each acceptance records the version, so you can always tell which wording a user agreed to.",
    )

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "consent text (signup checkbox)"
        verbose_name_plural = "consent texts (signup checkboxes)"

    def clean(self):
        from urllib.parse import urlsplit

        url = (self.url or "").strip()
        if url:
            scheme = urlsplit(url).scheme
            if scheme not in ("https",) and not url.startswith("/"):
                raise ValidationError({"url": "Use an https:// URL or a local path starting with /."})

    def __str__(self) -> str:
        return self.title


class UserConsent(models.Model):
    """Accepted consent, with a snapshot of the text at acceptance time.

    Read-only record: created automatically when a user ticks a consent
    text checkbox at registration. Do not edit by hand - it is the proof
    of what exactly was agreed to and when."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="consents", on_delete=models.CASCADE)
    slug = models.CharField(max_length=80)
    title = models.CharField(max_length=160)
    version = models.PositiveSmallIntegerField(default=1)
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-accepted_at"]
        verbose_name = "user consent acceptance"
        verbose_name_plural = "user consent acceptances"
        constraints = [
            models.UniqueConstraint(fields=["user", "slug", "version"], name="unique_consent_version")
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.slug}v{self.version}"


class RegistrationField(models.Model):
    """Admin-defined profile field asked at registration (and completion).

    Why: you decide what you need from users. Every active row becomes one
    field on the signup form; required fields also force EXISTING users
    through /account/complete/ at their next visit, so accounts created
    before the field existed fill it in too. Values are stored on the
    user profile and appear in their data export."""

    KIND_TEXT = "text"
    KIND_TEXTAREA = "textarea"
    KIND_EMAIL = "email"
    KIND_PHONE = "phone"
    KIND_ADDRESS = "address"
    KIND_CHOICES = (
        (KIND_TEXT, "Single line"),
        (KIND_TEXTAREA, "Paragraph"),
        (KIND_EMAIL, "Email"),
        (KIND_PHONE, "Phone"),
        (KIND_ADDRESS, "Address block"),
    )

    label = models.CharField(max_length=120)
    slug = models.SlugField(max_length=60, unique=True, help_text="Stored key inside profile.extra_data.")
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default=KIND_TEXT)
    required = models.BooleanField(default=False)
    help_text = models.CharField(max_length=200, blank=True)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "signup form field"
        verbose_name_plural = "signup form fields"

    def __str__(self) -> str:
        return self.label


class LoginEvent(models.Model):
    """Technical login trace. Shown to the user, retained per config, never
    deleted early (minimum window is a data-protection baseline)."""

    METHOD_PASSWORD = "password"
    METHOD_EMAIL_OTP = "email_otp"
    METHOD_MAGIC = "magic"
    METHOD_ANONYMOUS = "anonymous"
    METHOD_CHOICES = (
        (METHOD_PASSWORD, "Password"),
        (METHOD_EMAIL_OTP, "Email code"),
        (METHOD_MAGIC, "Magic link"),
        (METHOD_ANONYMOUS, "Access code"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="login_events", on_delete=models.CASCADE)
    method = models.CharField(max_length=12, choices=METHOD_CHOICES, default=METHOD_PASSWORD)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "login trace"
        verbose_name_plural = "login traces"

    def __str__(self) -> str:
        return f"{self.user_id} {self.method} {self.created:%Y-%m-%d %H:%M}"


class DataExportRequest(models.Model):
    """GDPR export with deliberate friction: a waiting period before the
    archive is built, a download window, and a cooldown before the next
    request. Processing is throttled (one archive per maintenance pass)."""

    STATUS_WAITING = "waiting"
    STATUS_READY = "ready"
    STATUS_PURGED = "purged"
    STATUS_CHOICES = (
        (STATUS_WAITING, "Waiting"),
        (STATUS_READY, "Ready for download"),
        (STATUS_PURGED, "Purged"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="export_requests", on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_WAITING)
    created = models.DateTimeField(auto_now_add=True)
    ready_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    file = models.FileField(
        upload_to="exports/", storage=PrivateMediaStorage(), blank=True,
        help_text="Private storage: never reachable through /media/ or any public route.",
    )

    class Meta:
        ordering = ["-created"]
        verbose_name = "data export request"
        verbose_name_plural = "data export requests"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def delete(self, *args, **kwargs):
        """Remove the archive bytes with the row: Django does not delete
        files for you, and orphaned exports must never outlive the request."""
        if self.file:
            self.file.delete(save=False)
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return f"export:{self.user_id}:{self.status}"


class MagicLink(models.Model):
    """Single-use magic sign-in tokens, hashed at rest and consumed
    atomically in the database so replay is impossible across workers."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="magic_links", on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    @classmethod
    def issue(cls, user, ttl_seconds: int) -> "tuple[str, MagicLink]":
        import secrets
        from datetime import timedelta

        from django.utils import timezone as tz

        raw = secrets.token_urlsafe(32)
        link = cls.objects.create(
            user=user,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires=tz.now() + timedelta(seconds=ttl_seconds),
        )
        return raw, link

    def consume(self) -> bool:
        """Atomic single-use: the conditional update wins for exactly one
        request, even with concurrent clicks or multiple workers."""
        from django.utils import timezone as tz

        if self.consumed_at or self.expires < tz.now():
            return False
        updated = type(self).objects.filter(pk=self.pk, consumed_at__isnull=True).update(
            consumed_at=tz.now()
        )
        return bool(updated)

    def __str__(self) -> str:
        return f"magic:{self.user_id}"
