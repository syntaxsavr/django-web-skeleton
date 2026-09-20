"""Context processors: expose configuration, navigation and footer records."""

from django.db.models import Prefetch
from django.urls import reverse

from core.models import FooterItem, FooterSection, NavigationItem, SiteConfiguration


PAGE_ROUTES = {
    FooterItem.PAGE_HOME: "home",
    FooterItem.PAGE_DEMO: "demo",
    FooterItem.PAGE_ARTICLES: "articles",
    FooterItem.PAGE_CONTACT: "contact",
    FooterItem.PAGE_ACCOUNT: "account_dashboard",
    FooterItem.PAGE_LOGIN: "login",
    FooterItem.PAGE_REGISTER: "register",
    FooterItem.PAGE_PRIVACY: "privacy",
    FooterItem.PAGE_IMPRINT: "imprint",
    FooterItem.PAGE_ACCESSIBILITY: "accessibility",
    FooterItem.PAGE_ROBOTS: "robots_txt",
    FooterItem.PAGE_LLMS: "llms_txt",
    FooterItem.PAGE_LLMS_FULL: "llms_full_txt",
    FooterItem.PAGE_SECURITY: "security_txt_wellknown",
    FooterItem.PAGE_HUMANS: "humans_txt",
}

A11Y_ACTIONS = {
    FooterItem.ACTION_DARK: "toggle-dark",
    FooterItem.ACTION_TEXT: "toggle-text",
    FooterItem.ACTION_MOTION: "toggle-motion",
    FooterItem.ACTION_PRINT: "print-page",
}

NAVIGATION_ROUTES = {
    NavigationItem.PAGE_HOME: "home",
    NavigationItem.PAGE_DEMO: "demo",
    NavigationItem.PAGE_ARTICLES: "articles",
    NavigationItem.PAGE_CONTACT: "contact",
    NavigationItem.PAGE_ACCOUNT: "account_dashboard",
    NavigationItem.PAGE_LOGIN: "login",
    NavigationItem.PAGE_REGISTER: "register",
    NavigationItem.PAGE_PRIVACY: "privacy",
    NavigationItem.PAGE_IMPRINT: "imprint",
    NavigationItem.PAGE_ACCESSIBILITY: "accessibility",
}


def _navigation_item_visible(item, config, request):
    if item.page == NavigationItem.PAGE_ARTICLES:
        return config.enable_articles
    if item.page == NavigationItem.PAGE_CONTACT:
        return config.enable_contact_form
    if item.page == NavigationItem.PAGE_REGISTER:
        return config.enable_public_registration and not request.user.is_authenticated
    if item.page == NavigationItem.PAGE_LOGIN:
        return not request.user.is_authenticated
    if item.page in (NavigationItem.PAGE_ACCOUNT, NavigationItem.PAGE_LOGOUT):
        return request.user.is_authenticated
    return True


def _navigation_item_url(item):
    if item.page == NavigationItem.PAGE_CUSTOM:
        return item.url
    if item.page == NavigationItem.PAGE_ADMIN:
        return "/admin/"
    route = NAVIGATION_ROUTES.get(item.page)
    return reverse(route) if route else ""


def _navigation_groups(config, request):
    if not config.enable_megamenu:
        return []
    groups = []
    group_lookup = {}
    for item in config.navigation_items.filter(active=True).order_by("sort_order", "pk"):
        if not _navigation_item_visible(item, config, request):
            continue
        title = item.group.strip() or "Menu"
        if title not in group_lookup:
            group_lookup[title] = {"title": title, "items": []}
            groups.append(group_lookup[title])
        group_lookup[title]["items"].append(
            {
                "label": item.label,
                "description": item.description,
                "url": _navigation_item_url(item),
                "is_logout": item.page == NavigationItem.PAGE_LOGOUT,
            }
        )
    return groups


def _footer_item_visible(item, config, request):
    if item.kind == FooterItem.KIND_ACTION:
        if item.action == FooterItem.ACTION_COOKIE:
            return config.enable_cookie_consent
        if item.action == FooterItem.ACTION_LOGOUT:
            return request.user.is_authenticated
        return True
    if item.kind != FooterItem.KIND_LINK:
        return True
    if item.page == FooterItem.PAGE_ARTICLES:
        return config.enable_articles
    if item.page == FooterItem.PAGE_CONTACT:
        return config.enable_contact_form
    if item.page == FooterItem.PAGE_REGISTER:
        return config.enable_public_registration and not request.user.is_authenticated
    if item.page == FooterItem.PAGE_LOGIN:
        return not request.user.is_authenticated
    if item.page == FooterItem.PAGE_ROBOTS:
        return config.enable_robots_txt
    if item.page == FooterItem.PAGE_SITEMAP:
        return config.enable_sitemap
    if item.page in (FooterItem.PAGE_LLMS, FooterItem.PAGE_LLMS_FULL):
        return config.enable_llms_txt
    return True


def _footer_item_url(item):
    if item.page == FooterItem.PAGE_CUSTOM:
        return item.url
    if item.page == FooterItem.PAGE_ADMIN:
        return "/admin/"
    if item.page == FooterItem.PAGE_SITEMAP:
        return "/sitemap.xml"
    route = PAGE_ROUTES.get(item.page)
    return reverse(route) if route else ""


def _footer_sections(config, request):
    if not config.enable_footer:
        return []
    sections = FooterSection.objects.filter(active=True).prefetch_related(
        Prefetch("items", queryset=FooterItem.objects.filter(active=True).order_by("sort_order", "pk"))
    )
    rendered = []
    for section in sections:
        items = []
        for item in section.items.all():
            if not _footer_item_visible(item, config, request):
                continue
            items.append(
                {
                    "kind": item.kind,
                    "quiet": item.quiet,
                    "label": item.label,
                    "url": _footer_item_url(item) if item.kind in (FooterItem.KIND_LINK, FooterItem.KIND_MEDIA) else "",
                    "text": item.text,
                    "media_url": item.media.url if item.media else "",
                    "media_alt": item.media_alt,
                    "action": item.action,
                    "a11y_action": A11Y_ACTIONS.get(item.action, ""),
                    "is_cookie_action": item.action == FooterItem.ACTION_COOKIE,
                    "is_logout_action": item.action == FooterItem.ACTION_LOGOUT,
                }
            )
        if items:
            rendered.append({"title": section.title, "items": items})
    return rendered


def site_settings(request):
    config = getattr(request, "site_config", None) or SiteConfiguration.get_solo()
    return {
        "site_config": config,
        "site_name": config.site_name,
        "canonical_origin": config.canonical_origin.rstrip("/"),
        "turnstile_site_key": config.effective_turnstile_site_key if config.enable_turnstile else "",
        "turnstile_on": config.enable_turnstile,
        "enable_honeypot": config.enable_honeypot,
        "enable_registration": config.enable_public_registration,
        "enable_articles": config.enable_articles,
        "enable_contact": config.enable_contact_form,
        "enable_stripe": config.enable_stripe_buy_button and bool(config.stripe_publishable_key),
        "enable_tracking": config.enable_tracking,
        "enable_consent": config.enable_cookie_consent,
        "enable_external_link_modal": config.enable_external_link_handling and config.external_link_modal,
        "protected_title": request.session.get("protected_page_title", ""),
        "footer_sections": _footer_sections(config, request),
        "navigation_groups": _navigation_groups(config, request),
    }


def tracking_configuration(request):
    config = getattr(request, "site_config", None) or SiteConfiguration.get_solo()
    return {"tracking": config, "tracking_data": config.tracking_data()}
