"""SEO template tags: JSON-LD structured data, emitted only when the
control panel has enable_jsonld on. All JSON goes through json_script-style
escaping (< becomes \\u003c) so the CSP-safe script blocks stay valid."""

import json

from django import template
from django.urls import reverse
from django.utils.html import format_html

from core.models import SiteConfiguration

register = template.Library()


def _script(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return format_html('<script type="application/ld+json">{}</script>', payload)


@register.simple_tag(takes_context=True)
def organization_schema(context):
    config = _config(context)
    if not config.enable_jsonld:
        return ""
    origin = config.canonical_origin.rstrip("/")
    return _script(
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "@id": origin + "/#organization",
            "name": config.site_name,
            "url": origin + "/",
        }
    )


@register.simple_tag(takes_context=True)
def seo_breadcrumbs(context):
    config = _config(context)
    if not config.enable_jsonld:
        return ""
    request = context.get("request")
    if request is None or not getattr(request, "resolver_match", None):
        return ""
    url_name = request.resolver_match.url_name or ""
    if url_name == "home":
        return ""

    origin = config.canonical_origin.rstrip("/")
    labels = {
        "home": "Home",
        "demo": "Demo",
        "contact": "Contact",
        "privacy": "Privacy",
        "imprint": "Imprint",
        "accessibility": "Accessibility",
        "account_dashboard": "Account",
    }
    label = labels.get(url_name)
    if label is None:
        return ""

    items = [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": origin + "/"},
        {"@type": "ListItem", "position": 2, "name": label, "item": origin + request.path},
    ]
    return _script({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items})


def _config(context):
    request = context.get("request")
    return getattr(request, "site_config", None) or SiteConfiguration.get_solo()


@register.simple_tag(takes_context=True)
def canonical_url(context):
    request = context.get("request")
    origin = _config(context).canonical_origin.rstrip("/")
    path = request.path if request else "/"
    return origin + path
