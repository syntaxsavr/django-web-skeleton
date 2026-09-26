"""Privacy center: data export with deliberate friction, scheduled data
deletion and account deletion. Both destructive flows use the same two
steps: email code, then typing an uncopyable confirmation sentence."""

import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.authhelpers import hash_code, issue_user_code, resend_throttled, send_site_mail
from accounts.forms import CodeForm
from accounts.models import DataExportRequest, UserProfile
from core.models import SiteConfiguration
from core.views.helpers import site_config

CONFIRMATION_FRESHNESS = 10 * 60  # seconds

PHRASE_VERBS = ("erase", "remove", "purge", "wipe", "delete")
PHRASE_OBJECTS = ("my data", "my profile", "my details", "my information")


def _phrase(request, key: str) -> str:
    """One uncopyable confirmation sentence per attempt. Stored in the
    session so the POST can compare; rendered split so selecting it is
    useless (and we tell people to type it)."""
    phrase = request.session.get(key)
    if not phrase:
        verb = secrets.choice(PHRASE_VERBS)
        obj = secrets.choice(PHRASE_OBJECTS)
        filler = secrets.randbelow(9000) + 1000
        phrase = f"I hereby {verb} {obj} and confirm with the number {filler}."
        request.session[key] = phrase
        request.session[key + "_created"] = timezone.now().isoformat()
    return phrase


def _check_step_one(request, purpose: str) -> bool:
    """True only while the email-code confirmation is FRESH: a browser left
    open cannot skip the email step hours or days later."""
    confirmed_at = request.session.get("confirmed_" + purpose)
    if not confirmed_at:
        return False
    try:
        age = (timezone.now() - timezone.datetime.fromisoformat(confirmed_at)).total_seconds()
    except (ValueError, TypeError):
        return False
    return age <= CONFIRMATION_FRESHNESS


def _reset_steps(request, purpose: str):
    for key in ("confirmed_" + purpose, "phrase_" + purpose, "phrase_" + purpose + "_created"):
        request.session.pop(key, None)


@login_required
def privacy_center(request):
    config = site_config(request)
    profile = UserProfile.for_user(request.user)
    latest = request.user.export_requests.first()
    cooldown_until = None
    can_request = True
    if latest:
        cooldown_until = latest.created + timedelta(days=config.export_cooldown_days)
        can_request = timezone.now() >= cooldown_until
    pending_phrase = None
    if request.session.get("phrase_data_deletion"):
        pending_phrase = request.session["phrase_data_deletion"]
    return render(
        request,
        "accounts/privacy_center.html",
        {
            "page_title": "Privacy center",
            "latest_export": latest,
            "can_request_export": can_request,
            "cooldown_until": cooldown_until,
            "export_wait_minutes": config.export_wait_minutes,
            "profile": profile,
            "deletion_pending": bool(profile.data_deletion_at or profile.account_deletion_at),
        },
    )


@login_required
def export_request(request):
    config = site_config(request)
    if request.method != "POST":
        return redirect("privacy_center")
    latest = request.user.export_requests.first()
    if latest:
        cooldown_until = latest.created + timedelta(days=config.export_cooldown_days)
        if timezone.now() < cooldown_until:
            messages.error(
                request,
                "You can request your next archive on %s." % cooldown_until.strftime("%d %B %Y"),
            )
            return redirect("privacy_center")
    now = timezone.now()
    entry = DataExportRequest.objects.create(
        user=request.user,
        ready_at=now + timedelta(minutes=config.export_wait_minutes),
        expires_at=now + timedelta(days=config.export_retention_days),
    )
    messages.info(
        request,
        "Got it. Building your archive takes a while - expect it in about %d minutes. "
        "This page shows a download button as soon as it is ready." % config.export_wait_minutes,
    )
    return redirect("privacy_center")


@login_required
def export_download(request, pk):
    entry = get_object_or_404(DataExportRequest, pk=pk, user=request.user)
    if entry.status != DataExportRequest.STATUS_READY or not entry.file:
        raise Http404
    if timezone.now() > entry.expires_at:
        entry.file.delete(save=False)
        entry.status = DataExportRequest.STATUS_PURGED
        entry.save(update_fields=["status", "file"])
        raise Http404
    response = FileResponse(entry.file.open("rb"), as_attachment=True, filename="my-data.json.gz")
    return response


# --- shared two-step confirmation -------------------------------------------------


def _confirmation_page(request, purpose: str, template: str, context: dict):
    email = request.user.email if not request.user.profile.mailhashed else ""
    step = 2 if _check_step_one(request, purpose) else 1
    context.update(
        {
            "step": step,
            "purpose": purpose,
            "has_email": bool(email),
            "code_sent": bool(request.session.get("code_sent_" + purpose)),
            "page_title": context.get("page_title", "Confirm"),
        }
    )
    if step == 2:
        context["phrase"] = _phrase(request, "phrase_" + purpose)
    return render(request, template, context)


def _handle_confirmation_post(request, purpose: str, success_redirect: str):
    """Step logic shared by data and account deletion."""
    if request.POST.get("action") == "request_code":
        if request.user.profile.mailhashed or not request.user.email:
            messages.error(request, "This account has no usable email address. An administrator has to help you.")
            return redirect("privacy_center")
        code = issue_user_code(request.user, purpose)
        send_site_mail(
            request,
            request.user.email,
            "Confirmation code",
            f"Your confirmation code is {code}\nIt is valid for 15 minutes.",
        )
        messages.info(request, "A confirmation code is on its way to your email address.")
        return redirect(request.path)
    if request.POST.get("action") == "verify_code":
        from accounts.views.auth import _consume_user_code

        if _consume_user_code(request.user, purpose, request.POST.get("code", "")):
            request.session["confirmed_" + purpose] = timezone.now().isoformat()
            request.session.pop("phrase_" + purpose, None)
            request.session.pop("code_sent_" + purpose, None)
            return redirect(request.path)
        cache.set(attempt_key, attempts + 1, 16 * 60)
        messages.error(request, "That code is wrong or expired.")
        return redirect(request.path)
    if request.POST.get("action") == "confirm_phrase":
        if not _check_step_one(request, purpose):
            return redirect(request.path)
        expected = (request.session.get("phrase_" + purpose) or "").strip()
        typed = " ".join((request.POST.get("phrase") or "").split())
        if expected and secrets.compare_digest(typed, expected):
            request.session.pop("phrase_" + purpose, None)
            request.session.pop("confirmed_" + purpose, None)
            return None  # caller executes the action
        messages.error(request, "The confirmation sentence does not match. Check it letter by letter.")
        return redirect(request.path)
    return redirect("privacy_center")


@login_required
def data_deletion(request):
    config = site_config(request)
    profile = UserProfile.for_user(request.user)
    if profile.account_deletion_at or profile.data_deletion_at:
        messages.info(request, "A deletion is already scheduled for this account.")
        return redirect("privacy_center")
    if request.method == "POST":
        outcome = _handle_confirmation_post(request, "data_deletion", "privacy_center")
        if outcome is not None:
            return outcome
        now = timezone.now()
        delay = timedelta(hours=config.deletion_delay_hours)
        profile.data_deletion_requested = now
        profile.data_deletion_at = now + delay
        profile.suspended_by_data_deletion = True
        profile.save(update_fields=["data_deletion_requested", "data_deletion_at", "suspended_by_data_deletion", "updated"])
        request.user.is_active = False  # suspended until the deletion executes
        request.user.save(update_fields=["is_active"])
        logout(request)
        request.session.flush()
        messages.info(
            request,
            "Your data deletion is scheduled. For security reasons it executes in %d hours and "
            "the account stays suspended until then." % config.deletion_delay_hours,
        )
        return redirect("home")
    return _confirmation_page(
        request,
        "data_deletion",
        "accounts/confirm_deletion.html",
        {
            "mode": "data",
            "title": "Delete my data",
            "intro": "This removes your profile details, consents and export archives. Technical login "
            "traces are kept for their full retention window, and the deletion itself waits "
            "72 hours for security reasons. Your account is suspended until then.",
        },
    )


@login_required
def account_deletion(request):
    config = site_config(request)
    profile = UserProfile.for_user(request.user)
    if profile.account_deletion_at or profile.data_deletion_at:
        messages.info(request, "A deletion is already scheduled for this account.")
        return redirect("privacy_center")
    if request.method == "POST":
        outcome = _handle_confirmation_post(request, "account_deletion", "privacy_center")
        if outcome is not None:
            return outcome
        now = timezone.now()
        delay = timedelta(hours=config.deletion_delay_hours)
        profile.account_deletion_at = now + delay
        profile.save(update_fields=["account_deletion_at", "updated"])
        # Suspended immediately: other sessions must not stay usable while
        # deletion is pending, and the account can never be reactivated.
        request.user.is_active = False
        request.user.save(update_fields=["is_active"])
        logout(request)
        request.session.flush()
        messages.info(
            request,
            "Account deletion is scheduled. In %d hours your data is removed and the account is "
            "deactivated. It cannot be reactivated; you would register again." % config.deletion_delay_hours,
        )
        return redirect("home")
    return _confirmation_page(
        request,
        "account_deletion",
        "accounts/confirm_deletion.html",
        {
            "mode": "account",
            "title": "Delete my account",
            "intro": "Your data is removed and the account is deactivated after 72 hours. The account "
            "cannot be reactivated afterwards; if you ever come back, you register again. "
            "During the 72 hours the account stays suspended.",
        },
    )
