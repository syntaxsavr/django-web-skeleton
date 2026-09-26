"""Accounts middleware: auth master switch, forced 2FA for users,
forced profile completion."""

from django.http import Http404
from django.shortcuts import redirect

from accounts.models import UserProfile
from core.views.helpers import site_config

EXEMPT_PREFIXES = (
    "/account/complete/",
    "/account/two-factor/",
    "/accounts/logout/",
    "/admin/",
    "/static/",
    "/media/",
)


class AccountsMiddleware:
    """enable_accounts off means the whole account surface answers 404 and
    nothing about it leaks into navigation (context processor handles that)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not site_config(request).enable_accounts:
            path = request.path
            if path.startswith(("/accounts/", "/account/")):
                raise Http404
        return self.get_response(request)


class UserGateMiddleware:
    """After-login requirements, enforced while browsing:

    - force_2fa_users: every account needs a confirmed second factor
      (staff are covered by Staff2FAMiddleware with the same interlock).
    - required registration fields introduced after signup: the user is
      sent to the completion page until they are filled.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and user.is_active):
            return None
        path = request.path
        if not path.startswith("/account/") or any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return None
        config = site_config(request)
        profile = UserProfile.for_user(user)

        if config.force_2fa_users and not getattr(user, "otp_device", None):
            request.session["two_factor_next"] = path
            return redirect("two_factor_setup")

        if profile.missing_required_fields():
            return redirect("account_complete")
        return None
