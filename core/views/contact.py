"""Contact form delivery and anti-spam checks."""

import time

import requests
from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from core.forms import ContactForm
from core.views.helpers import site_config

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
FORM_TS_SALT = "skeleton.form_ts"
CONTACT_RATE_KEY = "contact_last_submit"


def _form_filled_too_fast(request, form_ts, min_seconds):
    try:
        loaded = float(signing.loads(form_ts, salt=FORM_TS_SALT, max_age=7200))
    except (signing.BadSignature, ValueError, TypeError, OverflowError):
        return True
    return (time.time() - loaded) < min_seconds


def _turnstile_ok(request, config):
    if not config.enable_turnstile:
        return True
    secret = config.effective_turnstile_secret_key
    if not secret:
        return True
    token = request.POST.get("cf_turnstile_response", "")
    if not token:
        return False
    try:
        response = requests.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": secret, "response": token, "remoteip": request.META.get("REMOTE_ADDR", "")},
            timeout=8,
        )
        return bool(response.json().get("success"))
    except (requests.RequestException, ValueError):
        return True


def contact(request):
    config = site_config(request)
    if not config.enable_contact_form:
        raise Http404

    rate_key = "%s_%s" % (CONTACT_RATE_KEY, request.META.get("REMOTE_ADDR", "anon"))
    last = request.session.get(rate_key, 0)
    cooldown = config.contact_rate_limit_seconds
    if request.method == "POST":
        remaining = int(cooldown - (time.time() - last))
        if remaining > 0:
            minutes, seconds = divmod(remaining, 60)
            wait = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
            messages.error(request, mark_safe(f"You can send another message in {wait}."))
            return redirect("contact")

    if request.method == "POST":
        form = ContactForm(request.POST)
        traps_ok = True
        if config.enable_honeypot and request.POST.get("website"):
            traps_ok = False
        elif _form_filled_too_fast(request, request.POST.get("form_ts", ""), config.form_min_seconds):
            traps_ok = False

        if not traps_ok:
            return redirect("contact_thanks")

        if form.is_valid() and _turnstile_ok(request, config):
            entry = form.save()
            request.session[rate_key] = time.time()
            request.session["contact_summary"] = {"name": entry.name, "email": entry.email}
            if config.contact_email:
                send_mail(
                    subject=f"[{config.site_name}] New contact message from {entry.name}",
                    message=render_to_string(
                        "core/email/notification_email.txt",
                        {"entry": entry, "config": config},
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[config.contact_email],
                    fail_silently=True,
                )
                send_mail(
                    subject=f"[{config.site_name}] We received your message",
                    message=render_to_string(
                        "core/email/confirmation_email.txt",
                        {"entry": entry, "config": config},
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[entry.email],
                    fail_silently=True,
                )
            return redirect("contact_thanks")
    else:
        initial = {}
        if request.GET.get("preference") in ("email", "call"):
            initial["preference"] = request.GET["preference"]
        form = ContactForm(initial=initial)

    form.fields["form_ts"].initial = signing.dumps(time.time(), salt=FORM_TS_SALT)
    return render(
        request,
        "core/contact.html",
        {"form": form, "page_title": "Contact", "turnstile_on": config.enable_turnstile},
    )


def contact_thanks(request):
    if not site_config(request).enable_contact_form:
        raise Http404
    summary = request.session.pop("contact_summary", None)
    return render(request, "core/contact_thanks.html", {"summary": summary, "page_title": "Message sent"})
