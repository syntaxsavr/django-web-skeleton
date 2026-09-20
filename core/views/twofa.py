"""TOTP second factor: enrollment, verification and management.

Staff enforcement lives in core.middleware.Staff2FAMiddleware; these views
implement the flows it redirects to. Non-staff users can enroll voluntarily.
"""

import base64
import binascii
from io import BytesIO

import django_otp
import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from core.views.helpers import site_config


def _safe_next(request, fallback):
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return fallback


def _confirmed_device(user):
    for device in django_otp.devices_for_user(user):
        if device.confirmed:
            return device
    return None


def _qr_data_uri(text: str) -> str:
    image = qrcode.QRCode(box_size=6, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    image.add_data(text)
    image.make(fit=True)
    buffer = BytesIO()
    image.make_image(fill_color="#0a0a0a", back_color="#fcfcfa").save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _pending_target(request):
    """Where the enforcement middleware wants the user to end up."""
    target = request.session.pop("two_factor_next", "/admin/")
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = "/admin/"
    return target


def pending_redirect(request):
    """Called by Staff2FAMiddleware: route staff to the right 2FA step."""
    if _confirmed_device(request.user):
        url = reverse("two_factor_verify")
    else:
        url = reverse("two_factor_setup")
    request.session["two_factor_next"] = request.get_full_path()
    return HttpResponseRedirect(url)


@login_required
def two_factor_manage(request):
    device = _confirmed_device(request.user)
    enforced = getattr(settings, "ENFORCE_STAFF_2FA", False) and request.user.is_staff
    return render(
        request,
        "core/account/twofa_manage.html",
        {
            "page_title": "Two-factor authentication",
            "device": device,
            "enforced": enforced,
        },
    )


@login_required
def two_factor_setup(request):
    if _confirmed_device(request.user):
        messages.info(request, "Two-factor authentication is already active for your account.")
        return redirect("two_factor_manage")

    device = next(iter(django_otp.devices_for_user(request.user, confirmed=False)), None)
    if device is None:
        device = django_otp.plugins.otp_totp.models.TOTPDevice.objects.create(
            user=request.user, name="Authenticator app", confirmed=False
        )

    if request.method == "POST":
        token = request.POST.get("token", "").strip()
        if token and device.verify_token(token):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            django_otp.login(request, device)
            messages.success(request, "Two-factor authentication is now active.")
            if request.user.is_staff and getattr(settings, "ENFORCE_STAFF_2FA", False):
                return redirect(_pending_target(request))
            return redirect(_safe_next(request, reverse("two_factor_manage")))
        messages.error(request, "That code did not match. Codes rotate every 30 seconds; try the next one.")

    return render(
        request,
        "core/account/twofa_setup.html",
        {
            "page_title": "Set up two-factor authentication",
            "device": device,
            "qr_data_uri": _qr_data_uri(device.config_url),
            "secret": base64.b32encode(binascii.unhexlify(device.key)).decode("ascii").rstrip("="),
            "next": request.POST.get("next") or request.GET.get("next", ""),
            "pending_admin": request.user.is_staff
            and getattr(settings, "ENFORCE_STAFF_2FA", False)
            and request.session.get("two_factor_next", "").startswith("/admin/"),
        },
    )


@login_required
def two_factor_verify(request):
    device = _confirmed_device(request.user)
    if device is None:
        return redirect("two_factor_setup")

    if request.method == "POST":
        token = request.POST.get("token", "").strip()
        if token and device.verify_token(token):
            django_otp.login(request, device)
            messages.success(request, "Second factor verified.")
            if request.user.is_staff and getattr(settings, "ENFORCE_STAFF_2FA", False):
                return redirect(_pending_target(request))
            return redirect(_safe_next(request, reverse("account_dashboard")))
        messages.error(request, "That code did not match. Codes rotate every 30 seconds; try the next one.")

    return render(
        request,
        "core/account/twofa_verify.html",
        {
            "page_title": "Verify your second factor",
            "device": device,
            "next": request.POST.get("next") or request.GET.get("next", ""),
        },
    )


@login_required
def two_factor_remove(request):
    if request.method != "POST":
        return redirect("two_factor_manage")
    deleted, _count = django_otp.plugins.otp_totp.models.TOTPDevice.objects.filter(user=request.user).delete()
    if deleted:
        messages.info(request, "Two-factor authentication removed from your account.")
    else:
        messages.info(request, "No second factor was configured.")
    if request.user.is_staff and getattr(settings, "ENFORCE_STAFF_2FA", False):
        request.session["two_factor_next"] = "/admin/"
        return redirect("two_factor_setup")
    return redirect("two_factor_manage")
