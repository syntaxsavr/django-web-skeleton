"""Authentication, registration, account and email-OTP views."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from core.forms import RegistrationForm
from core.models import EmailCode
from core.views.helpers import site_config

OTP_TTL_MINUTES = 15
OTP_RESEND_COOLDOWN = 60


def _generate_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


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
    code = _generate_code()
    EmailCode.objects.create(
        user=user,
        code_hash=_hash_code(code),
        purpose="registration",
        expires=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    _send_otp(request, user, code)


def _too_many_requests(request):
    return render(request, "core/404.html", {"error_code": 429}, status=429)


class RateLimitedLoginView(auth_views.LoginView):
    template_name = "core/account/login.html"
    redirect_authenticated_user = True

    @method_decorator(ratelimit(key="ip", rate=settings.LOGIN_RATELIMIT, block=False))
    def dispatch(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            return _too_many_requests(request)
        return super().dispatch(request, *args, **kwargs)


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


@ratelimit(key="ip", rate=settings.REGISTER_RATELIMIT, block=False)
def register(request):
    config = site_config(request)
    if getattr(request, "limited", False):
        return _too_many_requests(request)
    if not config.enable_public_registration:
        raise Http404
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            User = get_user_model()
            if User.objects.filter(username=form.cleaned_data["username"]).exists():
                form.add_error("username", "This username is taken.")
            else:
                user = User.objects.create_user(
                    username=form.cleaned_data["username"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password1"],
                )
                if config.enable_email_otp:
                    user.is_active = False
                    user.save()
                    _issue_otp(request, user)
                    request.session["otp_user_pk"] = user.pk
                    messages.info(
                        request,
                        "We sent a six-digit code to your email address. Enter it below to activate your account.",
                    )
                    return redirect("registration_otp")
                if config.registration_requires_approval:
                    user.is_active = False
                    user.save()
                    messages.info(
                        request,
                        "Account created. An administrator has to activate it before you can sign in.",
                    )
                    return redirect("login")
                login(request, user)
                return redirect("account_dashboard")
    else:
        form = RegistrationForm()
    return render(request, "core/account/register.html", {"form": form, "page_title": "Create account"})


@login_required(login_url=reverse_lazy("login"))
def account_dashboard(request):
    return render(request, "core/account/dashboard.html", {"page_title": "Your account"})


def _otp_user(request):
    pk = request.session.get("otp_user_pk")
    if not pk:
        return None
    user = get_user_model().objects.filter(pk=pk, is_active=False).first()
    if user is None:
        request.session.pop("otp_user_pk", None)
    return user


def registration_otp(request):
    user = _otp_user(request)
    if user is None:
        return redirect("register")
    if request.method == "POST":
        code = (request.POST.get("code") or "").strip()
        entry = (
            EmailCode.objects.filter(user=user, purpose="registration", expires__gte=timezone.now())
            .order_by("-created")
            .first()
        )
        if entry and secrets.compare_digest(_hash_code(code), entry.code_hash):
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
