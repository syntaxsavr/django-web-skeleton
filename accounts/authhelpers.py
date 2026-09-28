"""Shared helpers for the authentication flows."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.utils import timezone

from accounts.models import LoginEvent, UserProfile
from core.models import SiteConfiguration

OTP_TTL_MINUTES = 15
RESEND_COOLDOWN = 60
OTP_MAX_ATTEMPTS = 6


def code_attempt(key: str, ok: bool) -> bool:
    """Count failed six-digit-code verifications; burn the code after
    OTP_MAX_ATTEMPTS failures so guessing is pointless. Call with ok=True
    on success (clears the counter), ok=False on every wrong try. Returns
    True while verification is still allowed."""
    cache_key = "otp_attempts_" + key
    if ok:
        cache.delete(cache_key)
        return True
    attempts = cache.get(cache_key, 0) + 1
    cache.set(cache_key, attempts, OTP_TTL_MINUTES * 60 + 60)
    return attempts < OTP_MAX_ATTEMPTS


def pending_profile_gate(request, user) -> bool:
    """Post-login gates shared by every method. Returns True when the user
    was redirected somewhere else (2FA enrollment, completion, suspension)."""
    profile = UserProfile.for_user(user)

    if profile.account_deletion_at or profile.data_deletion_at:
        messages.error(request, "This account is suspended pending a deletion request and cannot be used right now.")
        return True

    from django_otp import devices_for_user

    config = SiteConfiguration.get_solo()
    needs_2fa = config.force_2fa_users or (user.is_staff and getattr(settings, "ENFORCE_STAFF_2FA", False))
    if needs_2fa and not any(device.confirmed for device in devices_for_user(user)):
        request.session["two_factor_next"] = request.get_full_path()
        messages.info(request, "A second factor is required before you can continue.")
        return redirect("two_factor_setup")

    if profile.missing_required_fields():
        return redirect("account_complete")

    return False


def record_login(request, user, method: str = "password") -> None:
    LoginEvent.objects.create(
        user=user,
        method=method,
        ip_address=request.META.get("REMOTE_ADDR") or None,
        user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:200],
    )


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


def generate_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def send_site_mail(request, to: str, subject: str, body: str) -> None:
    config = SiteConfiguration.get_solo()
    send_mail(
        subject=f"[{config.site_name}] {subject}",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to],
        fail_silently=False,
    )


def issue_user_code(user, purpose: str) -> str:
    """Server-side code bound to an existing user (hashed at rest)."""
    from core.models import EmailCode

    code = generate_code()
    EmailCode.objects.create(
        user=user,
        code_hash=hash_code(code),
        purpose=purpose,
        expires=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    return code


def issue_session_code(request, email: str, purpose: str) -> str:
    """Code for an address that has no account yet: lives in the signed
    session, never in the database."""
    code = generate_code()
    request.session["pending_email_" + purpose] = {
        "email": email,
        "code_hash": hash_code(code),
        "expires": (timezone.now() + timedelta(minutes=OTP_TTL_MINUTES)).isoformat(),
    }
    return code


def resend_throttled(user_key: str) -> bool:
    cache_key = "otp_resend_" + user_key
    if cache.get(cache_key):
        return True
    cache.set(cache_key, 1, RESEND_COOLDOWN)
    return False
