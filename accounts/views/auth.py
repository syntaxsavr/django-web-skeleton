"""Authentication flows: identifier-aware password login, email-code and
magic-link logins with anti-enumeration, anonymous access codes, and the
dynamic registration.

Rule of the road: for code/magic flows the response NEVER reveals whether
an address has an account. Unknown addresses only proceed when
registration is open, and then straight into the normal registration.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.authhelpers import (
    generate_code,
    hash_code,
    issue_session_code,
    issue_user_code,
    pending_profile_gate,
    record_login,
    resend_throttled,
    send_site_mail,
)
from accounts.forms import CodeForm, DynamicRegistrationForm, EmailStartForm, IdentifierLoginForm
from accounts.models import UserConsent, UserProfile
from core.models import SiteConfiguration
from core.views.helpers import site_config

MAGIC_SALT = "accounts.magic"
MAGIC_TTL = 900


def _config(request):
    return site_config(request)


def _accounts_available(config) -> None:
    if not config.enable_accounts:
        raise Http404


def _user_by_identifier(config, identifier: str):
    User = get_user_model()
    mode = config.login_identifier_mode
    queryset = User.objects.all()
    if mode == "email":
        return queryset.filter(email__iexact=identifier).first()
    if mode == "username":
        return queryset.filter(username__iexact=identifier).first()
    return queryset.filter(models_q_email_or_username(identifier)).first()


def models_q_email_or_username(identifier: str):
    from django.db.models import Q

    return Q(email__iexact=identifier) | Q(username__iexact=identifier)


def _login_eligible(user) -> bool:
    """Suspended (pending deletion) accounts never log in."""
    profile = UserProfile.for_user(user)
    return user.is_active and not (profile.account_deletion_at or profile.data_deletion_at)


# --- Password login ----------------------------------------------------------


def login_view(request):
    config = _config(request)
    _accounts_available(config)
    if not config.enable_login_password:
        return redirect(_first_method_url(config) or "home")
    if request.user.is_authenticated:
        return redirect("account_dashboard")

    if request.method == "POST":
        form = IdentifierLoginForm(request.POST, mode=config.login_identifier_mode)
        if form.is_valid():
            user = _user_by_identifier(config, form.cleaned_data["identifier"])
            auth_user = None
            if user and not UserProfile.for_user(user).is_anonymous:
                auth_user = authenticate(
                    request, username=user.username, password=form.cleaned_data["password"]
                )
            if auth_user:
                if not _login_eligible(auth_user):
                    messages.error(
                        request,
                        "This account is suspended pending a deletion request and cannot be used right now.",
                    )
                else:
                    login(request, auth_user)
                    gate = pending_profile_gate(request, auth_user)
                    if gate:
                        return gate
                    record_login(request, auth_user)
                    return redirect(request.GET.get("next") or "account_dashboard")
            else:
                messages.error(request, "Those credentials did not match. Try again.")
    else:
        form = IdentifierLoginForm(mode=config.login_identifier_mode)
    return render(
        request,
        "accounts/login.html",
        {"form": form, "config": config, "page_title": "Sign in"},
    )


def _first_method_url(config) -> str:
    if config.enable_login_password:
        return "/accounts/login/"
    if config.enable_login_email_otp:
        return "/accounts/login/code/"
    if config.enable_login_magic_link:
        return "/accounts/login/magic/"
    if config.enable_login_anonymous:
        return "/accounts/login/token/"
    return ""


# --- Email code login (anti-enumeration) ---------------------------------------


@require_http_methods(["GET", "POST"])
def login_code_start(request):
    config = _config(request)
    _accounts_available(config)
    if not config.enable_login_email_otp:
        raise Http404
    generic = "If the address belongs to an account, a code is on its way. It expires in 15 minutes."
    if request.method == "POST":
        form = EmailStartForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = get_user_model().objects.filter(email__iexact=email).first()
            if user and _login_eligible(user) and not UserProfile.for_user(user).is_anonymous:
                code = issue_user_code(user, "login")
                send_site_mail(
                    request,
                    user.email,
                    "Your sign-in code",
                    f"Your code is {code}\nIt is valid for 15 minutes.\n\nIf you did not request it, ignore this message.",
                )
            request.session["code_login_email"] = email
            return redirect("login_code_verify")
    else:
        form = EmailStartForm()
    return render(request, "accounts/code_start.html", {"form": form, "notice": generic, "page_title": "Sign in with a code"})


@require_http_methods(["GET", "POST"])
def login_code_verify(request):
    config = _config(request)
    _accounts_available(config)
    if not config.enable_login_email_otp:
        raise Http404
    email = request.session.get("code_login_email")
    if not email:
        return redirect("login_code_start")

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if request.method == "POST":
        form = CodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"]
            if user and _login_eligible(user) and _consume_user_code(user, "login", code):
                login(request, user)
                request.session.pop("code_login_email", None)
                gate = pending_profile_gate(request, user)
                if gate:
                    return gate
                record_login(request, user, method="email_otp")
                return redirect(request.GET.get("next") or "account_dashboard")
            if not user and _consume_session_code(request, "login", code):
                # unknown address + valid code -> registration (if open)
                request.session.pop("code_login_email", None)
                if config.enable_public_registration:
                    request.session["pending_registration_email"] = signing.dumps(email, salt=MAGIC_SALT)
                    return redirect("register")
            messages.error(request, "That code is wrong or expired. Request a new one.")
    else:
        form = CodeForm()
    return render(
        request,
        "accounts/code_verify.html",
        {"form": form, "email": email, "resend_url": "login_code_start", "page_title": "Enter your code"},
    )


# --- Magic link ---------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def login_magic_start(request):
    config = _config(request)
    _accounts_available(config)
    if not config.enable_login_magic_link:
        raise Http404
    generic = "If the address belongs to an account, a sign-in link is on its way. It works once and for 15 minutes."
    if request.method == "POST":
        form = EmailStartForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = get_user_model().objects.filter(email__iexact=email).first()
            if user and _login_eligible(user) and not UserProfile.for_user(user).is_anonymous:
                token = signing.dumps({"u": user.pk}, salt=MAGIC_SALT)
                link = request.build_absolute_uri(f"/accounts/login/magic/{token}/")
                send_site_mail(
                    request,
                    user.email,
                    "Your sign-in link",
                    f"Sign in with this link (once, 15 minutes):\n\n{link}\n\nIf you did not request it, ignore this message.",
                )
            request.session["magic_sent"] = True
            return render(request, "accounts/magic_sent.html", {"notice": generic, "page_title": "Check your inbox"})
    else:
        form = EmailStartForm()
    return render(request, "accounts/code_start.html", {"form": form, "notice": generic, "magic": True, "page_title": "Sign in with a link"})


def login_magic_click(request, token):
    config = _config(request)
    _accounts_available(config)
    if not config.enable_login_magic_link:
        raise Http404
    from django.core.cache import cache

    if cache.get("magic_used_" + token):
        payload = None
    else:
        try:
            payload = signing.loads(token, salt=MAGIC_SALT, max_age=MAGIC_TTL)
        except signing.BadSignature:
            payload = None
    user = get_user_model().objects.filter(pk=(payload or {}).get("u", 0)).first() if payload else None
    if user and _login_eligible(user):
        cache.set("magic_used_" + token, 1, MAGIC_TTL)
        login(request, user)
        gate = pending_profile_gate(request, user)
        if gate:
            return gate
        record_login(request, user, method="magic")
        return redirect("account_dashboard")
    messages.error(request, "That sign-in link is invalid, used up or expired. Request a new one.")
    return redirect("login_magic_start")


# --- Anonymous access codes -----------------------------------------------------


@require_http_methods(["GET", "POST"])
def login_token(request):
    config = _config(request)
    _accounts_available(config)
    if not config.enable_login_anonymous:
        raise Http404
    if request.method == "POST":
        token = (request.POST.get("token") or "").strip()
        user = get_user_model().objects.filter(username__iexact=token).first()
        if user and UserProfile.for_user(user).is_anonymous and _login_eligible(user):
            login(request, user)
            gate = pending_profile_gate(request, user)
            if gate:
                return gate
            record_login(request, user, method="anonymous")
            return redirect(request.GET.get("next") or "account_dashboard")
        messages.error(request, "That access code is not valid.")
    return render(
        request,
        "accounts/token_login.html",
        {"register_open": config.enable_public_registration, "page_title": "Access code"},
    )


@require_http_methods(["POST"])
def token_register(request):
    config = _config(request)
    _accounts_available(config)
    if not config.enable_login_anonymous or not config.enable_public_registration:
        raise Http404
    length = max(12, min(64, config.anonymous_token_length))
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    token = "".join(secrets.choice(alphabet) for _ in range(length))
    User = get_user_model()
    user = User.objects.create_user(username=token)
    user.set_unusable_password()
    user.save()
    profile = UserProfile.for_user(user)
    profile.is_anonymous = True
    profile.save(update_fields=["is_anonymous", "updated"])
    login(request, user)
    record_login(request, user, method="anonymous")
    messages.info(request, "Store this access code somewhere safe. It is the only way into this account.")
    request.session["show_new_token"] = token
    return redirect("account_dashboard")


# --- Registration ---------------------------------------------------------------


def register(request):
    config = _config(request)
    _accounts_available(config)
    if not config.enable_public_registration:
        raise Http404  # no trace of registration when it is off
    if request.user.is_authenticated:
        return redirect("account_dashboard")

    pending_email = None
    raw_pending = request.session.get("pending_registration_email")
    if raw_pending:
        try:
            pending_email = signing.loads(raw_pending, salt=MAGIC_SALT, max_age=MAGIC_TTL * 2)
        except signing.BadSignature:
            pending_email = None

    method = "password"
    if pending_email:
        method = "code"
    elif not config.enable_login_password and (config.enable_login_email_otp or config.enable_login_magic_link):
        # registration without the password method only makes sense after a
        # verified code/magic step; send people there
        return redirect(_first_method_url(config) or "home")

    if request.method == "POST":
        data = request.POST.copy()
        if pending_email:
            data["email"] = pending_email
        form = DynamicRegistrationForm(
            data,
            needs_password=(method == "password"),
            email_locked=bool(pending_email),
        )
        if form.is_valid():
            User = get_user_model()
            email = pending_email or form.cleaned_data.get("email", "").lower()
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, "An account with this email already exists.")
            else:
                user = User.objects.create_user(
                    username=form.cleaned_data["username"],
                    email=email,
                    password=form.cleaned_data.get("password1") or None,
                )
                if not form.cleaned_data.get("password1"):
                    user.set_unusable_password()
                    user.save()
                profile = UserProfile.for_user(user)
                profile.extra_data = form.extra_data()
                profile.save(update_fields=["extra_data", "updated"])
                for consent in form.accepted_consents():
                    UserConsent.objects.create(user=user, **consent)
                request.session.pop("pending_registration_email", None)

                if config.enable_email_otp and email:
                    user.is_active = False
                    user.save(update_fields=["is_active"])
                    from core.views.auth import _issue_otp

                    _issue_otp(request, user)
                    request.session["otp_user_pk"] = user.pk
                    messages.info(request, "We sent a six-digit code to your email address to confirm it.")
                    return redirect("registration_otp")
                if config.registration_requires_approval:
                    user.is_active = False
                    user.save(update_fields=["is_active"])
                    messages.info(request, "Account created. An administrator has to activate it before you can sign in.")
                    return redirect("login")
                login(request, user)
                messages.success(request, "Welcome aboard!")
                return redirect("account_dashboard")
    else:
        initial = {"email": pending_email} if pending_email else None
        form = DynamicRegistrationForm(
            initial=initial, needs_password=(method == "password"), email_locked=bool(pending_email)
        )
    return render(
        request,
        "accounts/register.html",
        {"form": form, "pending_email": pending_email, "config": config, "page_title": "Create account"},
    )


# --- code consumption helpers ----------------------------------------------------


def _consume_user_code(user, purpose: str, code: str) -> bool:
    from core.models import EmailCode

    entry = (
        EmailCode.objects.filter(user=user, purpose=purpose, expires__gte=timezone.now())
        .order_by("-created")
        .first()
    )
    if entry and secrets.compare_digest(hash_code(code), entry.code_hash):
        EmailCode.objects.filter(user=user, purpose=purpose).delete()
        return True
    return False


def _consume_session_code(request, purpose: str, code: str) -> bool:
    pending = request.session.get("pending_email_" + purpose)
    if not pending or timezone.now() > timezone.datetime.fromisoformat(pending["expires"]):
        return False
    if secrets.compare_digest(hash_code(code), pending["code_hash"]):
        request.session.pop("pending_email_" + purpose, None)
        return True
    return False
