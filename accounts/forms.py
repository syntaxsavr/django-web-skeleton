"""Forms for the accounts app: identifier-aware login, dynamic
registration, consents, profile data. Every inbound string is sanitized."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.safestring import mark_safe

from accounts.models import ConsentText, RegistrationField, UserProfile
from core.sanitizers import clean_multiline, clean_text

User = get_user_model()

IDENTIFIER_LABELS = {
    "username": "Username",
    "email": "Email address",
    "either": "Username or email address",
}


def sanitize_value(kind: str, raw: str) -> str:
    if kind == RegistrationField.KIND_TEXTAREA or kind == RegistrationField.KIND_ADDRESS:
        return clean_multiline(raw)
    return clean_text(raw)


class IdentifierLoginForm(forms.Form):
    """Password login with the configured identifier."""

    identifier = forms.CharField(label="Username or email address", max_length=254)
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, mode="either", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["identifier"].label = IDENTIFIER_LABELS.get(mode, IDENTIFIER_LABELS["either"])

    def clean_identifier(self):
        return clean_text(self.cleaned_data["identifier"])


class EmailStartForm(forms.Form):
    """Step one of the code and magic-link logins (anti-enumeration)."""

    email = forms.EmailField(label="Email address")

    def clean_email(self):
        return clean_text(self.cleaned_data["email"]).lower()


class CodeForm(forms.Form):
    code = forms.CharField(label="Six-digit code", max_length=6)


class DynamicRegistrationForm(forms.Form):
    """Username/email/password plus admin-defined fields and consents.
    Which parts appear depends on the login method registering."""

    username = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    password1 = forms.CharField(widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(widget=forms.PasswordInput, required=False)

    def __init__(self, *args, needs_password=False, needs_username=True, email_locked=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.needs_password = needs_password
        self._consent_fields = []
        self._dynamic_fields = []
        for field in RegistrationField.objects.filter(active=True).order_by("sort_order", "pk"):
            name = "field_" + field.slug
            self._dynamic_fields.append((name, field))
            common = {"required": field.required, "help_text": field.help_text}
            if field.kind == RegistrationField.KIND_TEXTAREA:
                self.fields[name] = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **common)
            elif field.kind == RegistrationField.KIND_ADDRESS:
                self.fields[name] = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **common)
            elif field.kind == RegistrationField.KIND_EMAIL:
                self.fields[name] = forms.EmailField(**common)
            else:
                self.fields[name] = forms.CharField(**common)
        for consent in ConsentText.objects.filter(active=True).order_by("sort_order", "pk"):
            name = "consent_" + consent.slug
            self._consent_fields.append((name, consent))
            label = consent.title
            if consent.url:
                label = mark_safe(f'{consent.title} <a href="{consent.url}" target="_blank" rel="noopener">read</a>')
            self.fields[name] = forms.BooleanField(
                label=label, required=consent.required, help_text=consent.body
            )
        if not needs_password:
            del self.fields["password1"]
            del self.fields["password2"]
        if not needs_username:
            del self.fields["username"]
        elif email_locked and "email" in self.fields:
            self.fields["email"].disabled = True

    def clean_username(self):
        value = clean_text(self.cleaned_data.get("username", ""))
        if value and User.objects.filter(username__iexact=value).exists():
            raise forms.ValidationError("This username is taken.")
        return value

    def clean_email(self):
        value = clean_text(self.cleaned_data.get("email", "")).lower()
        if value and User.objects.filter(email__iexact=value).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return value

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        if self.needs_password:
            if not cleaned.get("password1"):
                raise forms.ValidationError("A password is required for this login method.")
            if cleaned.get("password1") != cleaned.get("password2"):
                raise forms.ValidationError("The two passwords do not match.")
        if not cleaned.get("username") and "username" in self.fields:
            import secrets

            cleaned["username"] = "user-" + secrets.token_hex(5)
        return cleaned

    def extra_data(self) -> dict:
        data = {}
        for name, field in self._dynamic_fields:
            raw = self.cleaned_data.get(name, "")
            data[field.slug] = sanitize_value(field.kind, raw)
        return data

    def accepted_consents(self):
        """[(slug, title, version)] for every consent present on the form
        that was ticked (or not required but still ticked)."""
        from django.utils import timezone

        accepted = []
        for name, consent in self._consent_fields:
            if self.cleaned_data.get(name):
                accepted.append({"slug": consent.slug, "title": consent.title, "version": consent.version})
        return accepted


class ProfileDataForm(forms.Form):
    """Completion/edit of the admin-defined fields."""

    def __init__(self, *args, profile: UserProfile, only_missing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        for field in RegistrationField.objects.filter(active=True).order_by("sort_order", "pk"):
            current = (profile.extra_data or {}).get(field.slug, "")
            if only_missing and str(current).strip():
                continue
            name = "field_" + field.slug
            common = {"required": False, "help_text": field.help_text, "initial": current}
            if field.kind == RegistrationField.KIND_TEXTAREA or field.kind == RegistrationField.KIND_ADDRESS:
                self.fields[name] = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **common)
            elif field.kind == RegistrationField.KIND_EMAIL:
                self.fields[name] = forms.EmailField(**common)
            else:
                self.fields[name] = forms.CharField(**common)

    def apply(self):
        data = dict(self.profile.extra_data or {})
        for name, _bound in self.fields.items():
            field = RegistrationField.objects.filter(slug=name[len("field_"):]).first()
            if field:
                data[field.slug] = sanitize_value(field.kind, self.cleaned_data.get(name, ""))
        self.profile.extra_data = data
        self.profile.save(update_fields=["extra_data", "updated"])


class AvatarForm(forms.Form):
    avatar = forms.ImageField(required=False)

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if not avatar:
            return None
        from core.models import SiteConfiguration

        config = SiteConfiguration.get_solo()
        if not config.allow_avatar_upload:
            raise forms.ValidationError("Avatar uploads are disabled on this site.")
        if avatar.size > config.avatar_max_kb * 1024:
            raise forms.ValidationError(f"Avatars are limited to {config.avatar_max_kb} KB.")
        return avatar
