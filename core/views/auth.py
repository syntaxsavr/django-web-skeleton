"""Password reset, logout and the registration email-OTP confirmation.

The login and registration VIEWS live in the accounts app (accounts/views);
this module only owns the flows the core app registers itself: the Django
auth views for password reset, logout, and confirming a registration code.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils import timezone
from django_ratelimit.decorators import ratelimit

from accounts.authhelpers import code_attempt
from core.models import EmailCode
from core.views.helpers import site_config

OTP_TTL_MINUTES = 15
OTP_RESEND_COOLDOWN = 60


def _send_otp(request, user, code: str) -> None:
    config = site_config(request)
    send_mail(
        subject=f"[{config.site_name}] Your confirmation code: {code}",
        message=(
            f"Hello {user.username},\n\nyour confirmation code is {code}. "
            f"It is valid for {OTP_TTL_MINUTES} minutes.\n\n"
            f"If you did not request it, ignore this message.\n\n{config.site_name}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def _issue_otp(request, user) -> None:
    from accounts.authhelpers import generate_code, hash_code

    code = generate_code()
    EmailCode.objects.create(
        user=user,
        code_hash=hash_code(code),
        purpose="registration",
        expires=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    _send_otp(request, user, code)


class LogoutView(auth_views.LogoutView):
    pass


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "core/account/password_reset.html"


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "core/account/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "core/account/password_reset_confirm.html"


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "core/account/password_reset_complete.html"


def _otp_user(request):
    pk = request.session.get("otp_user_pk")
    if not pk:
        return None
    user = get_user_model().objects.filter(pk=pk, is_active=False).first()
    if user is None:
        request.session.pop("otp_user_pk", None)
    return user


@ratelimit(key="ip", rate=settings.REGISTER_RATELIMIT, block=False)
def registration_otp(request):
    user = _otp_user(request)
    if user is None:
        return redirect("register")
    if request.method == "POST":
        if getattr(request, "limited", False):
            messages.error(request, "Too many attempts. Wait a few minutes and try again.")
            return redirect("registration_otp")
        code = (request.POST.get("code") or "").strip()
        entry = (
            EmailCode.objects.filter(user=user, purpose="registration", expires__gte=timezone.now())
            .order_by("-created")
            .first()
        )
        if entry:
            from accounts.authhelpers import hash_code

            if secrets.compare_digest(hash_code(code), entry.code_hash):
                code_attempt("registration_%d" % user.pk, True)
                user.is_active = True
                user.save(update_fields=["is_active"])
                EmailCode.objects.filter(user=user, purpose="registration").delete()
                request.session.pop("otp_user_pk", None)
                config = site_config(request)
                if config.registration_requires_approval:
                    user.is_active = False
                    user.save(update_fields=["is_active"])
                    messages.info(request, "Email confirmed. An administrator has to activate your account.")
                    return redirect("login")
                login(request, user)
                messages.success(request, "Email confirmed. Welcome aboard!")
                return redirect("account_dashboard")
        # Burn the code after too many wrong guesses (shared counter).
        if not code_attempt("registration_%d" % user.pk, False):
            EmailCode.objects.filter(user=user, purpose="registration").delete()
            request.session.pop("otp_user_pk", None)
            messages.error(
                request, "Too many wrong codes. The code is invalidated - start the registration again."
            )
            return redirect("register")
        messages.error(request, "That code is wrong or expired. Request a new one below.")
    return render(request, "core/account/register_confirm.html", {"page_title": "Confirm your email"})


@ratelimit(key="ip", rate="3/5m", block=False)
def registration_otp_resend(request):
    user = _otp_user(request)
    if user is None:
        return redirect("register")
    if getattr(request, "limited", False):
        messages.error(request, "Too many codes requested. Wait a few minutes and try again.")
        return redirect("registration_otp")
    cache_key = "otp_resend_" + str(user.pk)
    if cache.get(cache_key):
        messages.error(request, "Please wait a minute before requesting another code.")
        return redirect("registration_otp")
    cache.set(cache_key, 1, OTP_RESEND_COOLDOWN)
    _issue_otp(request, user)
    messages.info(request, "A new code is on its way.")
    return redirect("registration_otp")
