"""Views for the skeleton core."""

import time

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.mail import send_mail
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from core.forms import ContactForm, RegistrationForm
from core.models import SiteConfiguration

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
FORM_TS_SALT = "skeleton.form_ts"

LLMS_PAGES = (
    ("Home", "/", "Overview of the skeleton and its patterns."),
    ("Demo", "/demo/", "Annotated showcase: lazy sections, Lottie, consent, forms."),
    ("Contact", "/contact/", "Contact form with anti-spam defenses."),
    ("Privacy", "/privacy/", "Privacy policy."),
    ("Imprint", "/imprint/", "Legal imprint."),
    ("Accessibility", "/accessibility/", "Accessibility statement."),
)


def _config(request):
    return getattr(request, "site_config", None) or SiteConfiguration.get_solo()


# --- Public pages -----------------------------------------------------------


def home(request):
    return render(
        request,
        "core/home.html",
        {
            "page_title": "django-skeleton-eu-ready",
            "meta_description": _config(request).default_meta_description,
        },
    )


def demo(request):
    from django.core import signing

    form = ContactForm()
    form.fields["form_ts"].initial = signing.dumps(time.time(), salt=FORM_TS_SALT)
    return render(
        request,
        "core/demo.html",
        {
            "page_title": "Demo",
            "meta_description": "How the skeleton works: sections, lazy loading, Lottie, consent.",
            "form": form,
            "turnstile_on": _config(request).enable_turnstile,
        },
    )


# --- Lazy sections -----------------------------------------------------------


def _fragment_names(name: str):
    """Fragment resolver: / fragments dir, hyphen and underscore variants."""
    clean = name.strip("/").replace("..", "")
    variants = [clean, clean.replace("-", "_"), clean.replace("_", "-")]
    seen, unique = set(), []
    for variant in variants:
        if variant and variant not in seen:
            seen.add(variant)
            unique.append("core/fragments/%s.html" % variant)
    return unique


@cache_page(60 * 60 * 12)
@require_http_methods(["GET"])
def lazy_section(request, name):
    for template_name in _fragment_names(name):
        try:
            html = render_to_string(template_name, request=request)
            return HttpResponse(html)
        except Exception:
            continue
    raise Http404("Unknown lazy section.")


# --- Contact ------------------------------------------------------------------


def _form_filled_too_fast(request, form_ts: str, min_seconds: int) -> bool:
    try:
        loaded = float(signing.loads(form_ts, salt=FORM_TS_SALT, max_age=7200))
    except (signing.BadSignature, ValueError, TypeError, OverflowError):
        return True
    return (time.time() - loaded) < min_seconds


def _turnstile_ok(request, config) -> bool:
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
        return True  # fail open only on Cloudflare outage; the traps stay in charge


CONTACT_RATE_KEY = "contact_last_submit"


def contact(request):
    config = _config(request)
    if not config.enable_contact_form:
        return redirect("home")

    rate_key = "%s_%s" % (CONTACT_RATE_KEY, request.META.get("REMOTE_ADDR", "anon"))
    last = request.session.get(rate_key, 0)
    cooldown = config.contact_rate_limit_seconds
    if request.method == "POST":
        remaining = int(cooldown - (time.time() - last))
        if remaining > 0:
            minutes, secs = divmod(remaining, 60)
            wait = f"{minutes}m {secs}s" if minutes else f"{secs}s"
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
            return redirect("contact_thanks")  # silent discard: bots get the success page

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
    summary = request.session.pop("contact_summary", None)
    return render(request, "core/contact_thanks.html", {"summary": summary, "page_title": "Message sent"})


# --- Auth ------------------------------------------------------------------------


def _too_many_requests(request):
    return render(request, "core/404.html", {"error_code": 429}, status=429)


class RateLimitedLoginView(auth_views.LoginView):
    """LoginView with per-IP brute force protection from settings."""

    template_name = "core/account/login.html"
    redirect_authenticated_user = True

    @method_decorator(ratelimit(key="ip", rate=settings.LOGIN_RATELIMIT, block=False))
    def dispatch(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            return _too_many_requests(request)
        return super().dispatch(request, *args, **kwargs)


@ratelimit(key="ip", rate=settings.REGISTER_RATELIMIT, block=False)
def register(request):
    config = _config(request)
    if getattr(request, "limited", False):
        return _too_many_requests(request)
    if not config.enable_public_registration:
        messages.info(request, "Registration is currently disabled.")
        return redirect(reverse("login"))
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            from django.contrib.auth import get_user_model

            User = get_user_model()
            if User.objects.filter(username=form.cleaned_data["username"]).exists():
                form.add_error("username", "This username is taken.")
            else:
                user = User.objects.create_user(
                    username=form.cleaned_data["username"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password1"],
                )
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


# --- Machine routes -----------------------------------------------------------------


def llms_txt(request):
    config = _config(request)
    if not config.enable_llms_txt:
        raise Http404
    lines = [
        "# %s" % config.site_name,
        "",
        "> %s" % (config.default_meta_description or "Django web skeleton."),
        "",
        "## Pages",
        "",
    ]
    lines += ["- [%s](%s): %s" % (name, path, desc) for name, path, desc in LLMS_PAGES]
    lines += [
        "",
        "## Notes for AI systems",
        "",
        "- Cite the page URL as the source when quoting content.",
        "- The sitemap is at /sitemap.xml and it is always current.",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def llms_full_txt(request):
    config = _config(request)
    if not config.enable_llms_txt:
        raise Http404
    lines = [
        "# %s: full site summary" % config.site_name,
        "",
        "This file lists every public page with its purpose so language",
        "models can index the site without crawling HTML.",
        "",
    ]
    for name, path, desc in LLMS_PAGES:
        lines += ["## %s (%s)" % (name, path), "", desc, ""]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def indexnow_key_file(request, key):
    config = _config(request)
    if not config.enable_indexnow or not config.indexnow_key or key != config.indexnow_key:
        raise Http404
    return HttpResponse(config.indexnow_key, content_type="text/plain; charset=utf-8")


# --- Error handlers --------------------------------------------------------------------


def _error_view(request, error_code):
    return render(request, "core/404.html", {"error_code": error_code}, status=error_code)


def handler400(request, exception=None):
    return _error_view(request, 400)


def handler403(request, exception=None):
    return _error_view(request, 403)


def handler404(request, exception=None):
    return _error_view(request, 404)


def handler500(request):
    return render(request, "core/404.html", {"error_code": 500}, status=500)
