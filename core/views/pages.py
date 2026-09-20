"""Small public pages that do not own a separate feature area."""

import time

from django.core import signing
from django.shortcuts import render

from core.forms import ContactForm
from core.views.contact import FORM_TS_SALT
from core.views.helpers import site_config


def home(request):
    config = site_config(request)
    return render(
        request,
        "core/home.html",
        {
            "page_title": "django-skeleton",
            "meta_description": config.default_meta_description,
        },
    )


def demo(request):
    form = ContactForm()
    form.fields["form_ts"].initial = signing.dumps(time.time(), salt=FORM_TS_SALT)
    return render(
        request,
        "core/demo.html",
        {
            "page_title": "Demo",
            "meta_description": "How the skeleton works: sections, lazy loading, Lottie and consent.",
            "form": form,
            "turnstile_on": site_config(request).enable_turnstile,
        },
    )
