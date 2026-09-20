"""The middleware stack.

Ordering (as wired in skeleton/settings.py) and why:

1.  SecurityMiddleware        Django defaults first.
2.  ContentSecurityPolicyMiddleware   Policy is built from the control
                                      panel, so it must run after nothing
                                      custom (it loads its own config via
                                      get_solo when request.site_config is
                                      not set yet).
3.  SiteConfigurationMiddleware       Attaches request.site_config exactly
                                      once per request; every layer below
                                      reads it without extra queries.
4.  PersonalDataScraperBlockMiddleware 403 scrapers before anything expensive.
5.  SearchIndexingMiddleware   Adds X-Robots-Tag headers on responses.
6.  WhiteNoiseMiddleware       Serves static files; bypasses the rest when hit.
7.  GZipMiddleware             Outer wrapper for the response rewriters.
8.  ConditionalGetMiddleware   ETag/304 handling.
9.  SessionMiddleware          Needs to precede auth/language.
10. LanguageFromURLMiddleware  Optional /<code>/ prefix handling (inert
                              unless settings.ENABLE_BILINGUAL).
11. CommonMiddleware, 12. CsrfViewMiddleware, 13. AuthenticationMiddleware
14. ProtectedPageMiddleware    Needs request.user, so it sits after auth.
15. MessageMiddleware, 16. XFrameOptionsMiddleware
17. ExternalLinkMiddleware     Last = innermost: rewrites the final HTML
                              before gzip (outer) compresses it.

Admin paths are exempt from CSP and external-link rewriting: the Django
admin and its theme ship their own trusted inline scripts.
"""

import re
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

from core.models import ProtectedPage, SiteConfiguration

ADMIN_PREFIXES = ("/admin/",)

# Paths that carry personal data (legal pages): never indexed, never scraped.
PERSONAL_DATA_PATH_PREFIXES = (
    "/privacy/",
    "/imprint/",
    "/accessibility/",
)

# Never indexed, regardless of configuration.
NOINDEX_PATH_PREFIXES = (
    "/account/",
    "/accounts/",
    "/api/",
    "/lazy-section/",
    "/demo-api/",
) + ADMIN_PREFIXES + PERSONAL_DATA_PATH_PREFIXES

SCRAPER_USER_AGENTS = (
    "semrushbot",
    "ahrefsbot",
    "mj12bot",
    "dotbot",
    "petalbot",
    "serpstatbot",
    "dataforseobot",
    "python-requests",
    "python-urllib",
    "scrapy",
    "curl/",
    "wget",
    "httrack",
    "htttrack",
    "webcopier",
    "site sucker",
    "sitesucker",
)


def _config(request) -> SiteConfiguration:
    return getattr(request, "site_config", None) or SiteConfiguration.get_solo()


def _is_html(response) -> bool:
    content_type = response.get("Content-Type", "")
    return content_type.startswith("text/html")


def _is_admin(path: str) -> bool:
    return path.startswith(ADMIN_PREFIXES)


class SiteConfigurationMiddleware:
    """Attach the control panel singleton to the request, once."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.site_config = SiteConfiguration.get_solo()
        response = self.get_response(request)
        response["X-Config-Version"] = str(request.site_config.pk)
        return response


class ContentSecurityPolicyMiddleware:
    """Strict CSP, built from the trackers that are actually enabled.

    Fixing the classic static-policy problem: enabling self-hosted Matomo
    or any tracker in the admin automatically extends script-src and
    connect-src with the hosts that tracker needs. No 'unsafe-inline'
    in script-src; JSON payloads travel through json_script.
    """

    SCRIPT_HOSTS = {
        "googletagmanager": ("www.googletagmanager.com",),
        "google_analytics": ("www.googletagmanager.com",),
        "google_ads": ("www.googletagmanager.com", "googleads.g.doubleclick.net"),
        "meta_pixel": ("connect.facebook.net",),
        "linkedin": ("snap.licdn.com",),
        "microsoft_ads": ("bat.bing.com",),
        "clarity": ("www.clarity.ms",),
        "hotjar": ("static.hotjar.com", "script.hotjar.com"),
        "tiktok": ("analytics.tiktok.com",),
        "pinterest": ("s.pinimg.com", "ct.pinterest.com"),
        "x_pixel": ("static.ads-twitter.com",),
        "turnstile": ("challenges.cloudflare.com",),
        "calcom": ("app.cal.com", "*"),
        "stripe": ("js.stripe.com",),
    }
    CONNECT_HOSTS = {
        "google_analytics": ("www.google-analytics.com", "region1.google-analytics.com"),
        "google_ads": ("www.google.com", "googleads.g.doubleclick.net"),
        "clarity": ("www.clarity.ms",),
        "hotjar": ("*.hotjar.com",),
        "tiktok": ("analytics.tiktok.com",),
        "pinterest": ("ct.pinterest.com",),
        "x_pixel": ("analytics.twitter.com",),
    }
    IMG_HOSTS = {
        "google_analytics": ("www.google-analytics.com", "www.googletagmanager.com"),
        "google_ads": ("www.google.com", "googleads.g.doubleclick.net"),
        "meta_pixel": ("www.facebook.com",),
        "linkedin": ("px.ads.linkedin.com",),
        "microsoft_ads": ("bat.bing.com",),
        "pinterest": ("ct.pinterest.com",),
        "x_pixel": ("analytics.twitter.com", "t.co"),
    }
    FRAME_HOSTS = {
        "turnstile": ("challenges.cloudflare.com",),
        "calcom": ("app.cal.com",),
        "stripe": ("js.stripe.com",),
    }

    def __init__(self, get_response):
        self.get_response = get_response

    @classmethod
    def _enabled_trackers(cls, config: SiteConfiguration):
        ids = config.tracking_data()["ids"]
        enabled = set()
        tracker_fields = {
            "googletagmanager": "googleTagManagerId",
            "google_analytics": "googleAnalyticsId",
            "google_ads": "googleAdsId",
            "meta_pixel": "metaPixelId",
            "linkedin": "linkedinPartnerId",
            "microsoft_ads": "microsoftUetTagId",
            "clarity": "clarityProjectId",
            "hotjar": "hotjarSiteId",
            "tiktok": "tiktokPixelId",
            "pinterest": "pinterestTagId",
            "x_pixel": "xPixelId",
        }
        for tracker, field in tracker_fields.items():
            if ids.get(field):
                enabled.add(tracker)
        if ids.get("matomoUrl"):
            enabled.add("matomo")
        if config.enable_turnstile:
            enabled.add("turnstile")
        if config.enable_calcom_embed:
            enabled.add("calcom")
        if config.enable_stripe_buy_button:
            enabled.add("stripe")
        return enabled

    @classmethod
    def build_policy(cls, config: SiteConfiguration) -> str:
        enabled = cls._enabled_trackers(config)

        def collect(table):
            hosts = {"'self'"}
            for tracker in enabled:
                hosts.update(table.get(tracker, ()))
            if "matomo" in enabled and config.matomo_url:
                hosts.add(config.matomo_url.strip().rstrip("/"))
            return sorted(hosts)

        parts = [
            "default-src 'self'",
            f"script-src {' '.join(collect(cls.SCRIPT_HOSTS))}",
            "style-src 'self' 'unsafe-inline'",
            f"img-src {' '.join(collect(cls.IMG_HOSTS))} data:",
            f"connect-src {' '.join(collect(cls.CONNECT_HOSTS))}",
            "font-src 'self'",
            f"frame-src {' '.join(collect(cls.FRAME_HOSTS))}",
            "frame-ancestors 'none'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'"
            + (" https://checkout.stripe.com" if "stripe" in enabled else ""),
            "upgrade-insecure-requests",
        ]
        return "; ".join(parts)

    def __call__(self, request):
        response = self.get_response(request)
        config = _config(request)
        if config.enable_csp and not _is_admin(request.path) and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = self.build_policy(config)
        return response


class PersonalDataScraperBlockMiddleware:
    """403 scraper user agents on pages that carry personal data.

    Search engine crawlers stay allowed so the pages remain discoverable.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(PERSONAL_DATA_PATH_PREFIXES):
            config = _config(request)
            ua = request.META.get("HTTP_USER_AGENT", "").lower()
            if config.enable_scraper_block and (not ua.strip() or any(bot in ua for bot in SCRAPER_USER_AGENTS)):
                return self._forbidden()
        return self.get_response(request)

    @staticmethod
    def _forbidden():
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Access denied.")


class SearchIndexingMiddleware:
    """X-Robots-Tag headers, driven by the control panel."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        config = _config(request)
        path = request.path
        if config.robots_noindex_whole_site or path.startswith(NOINDEX_PATH_PREFIXES):
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response


PROTECTED_CACHE_KEY = "core:protected_pages:active"


class Staff2FAMiddleware:
    """Force a TOTP second factor before staff can reach /admin/.

    Active only when settings.ENFORCE_STAFF_2FA is on (default: whenever
    DEBUG is off). Staff who authenticated with just a password are bounced
    to the enrollment or verification flow under /account/two-factor/;
    admin logout stays reachable so nobody is trapped. Non-staff users and
    public pages are untouched.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not getattr(settings, "ENFORCE_STAFF_2FA", False):
            return None
        user = getattr(request, "user", None)
        if not (user is not None and user.is_authenticated and user.is_staff):
            return None
        path = request.path
        if not path.startswith(ADMIN_PREFIXES) or path == "/admin/logout/":
            return None
        if getattr(user, "otp_device", None) is not None:
            return None
        from core.views.twofa import pending_redirect

        return pending_redirect(request)


class ProtectedPageMiddleware:
    """Login wall. Rules come from the ProtectedPage table (admin-managed)."""

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _rules():
        rules = cache.get(PROTECTED_CACHE_KEY)
        if rules is None:
            rules = list(
                ProtectedPage.objects.filter(active=True).values_list("path", "match_type", "title")
            )
            cache.set(PROTECTED_CACHE_KEY, rules, 60)
        return rules

    @classmethod
    def invalidate_cache(cls):
        cache.delete(PROTECTED_CACHE_KEY)

    def __call__(self, request):
        if request.user.is_authenticated or request.path.startswith(ADMIN_PREFIXES):
            return self.get_response(request)

        path = request.path
        for rule_path, match_type, title in self._rules():
            if not rule_path:
                continue
            if match_type == ProtectedPage.MATCH_EXACT:
                hit = path == rule_path
            else:
                prefix = rule_path if rule_path.endswith("/") else rule_path + "/"
                hit = path.startswith(prefix)
            if hit:
                from django.contrib.auth.views import redirect_to_login

                request.session["protected_page_title"] = title
                return redirect_to_login(request.get_full_path())
        return self.get_response(request)


ANCHOR_RE = re.compile(r"<a\s[^>]*>", re.IGNORECASE)
HREF_RE = re.compile(r"href=(['\"])([^'\"]*)\1", re.IGNORECASE)
REL_RE = re.compile(r"rel=(['\"])([^'\"]*)\1", re.IGNORECASE)


class ExternalLinkMiddleware(MiddlewareMixin):
    """The outbound link snatcher.

    For every cross-origin anchor in a 200 HTML response:
      - adds data-external="true" (drives the optional leave-site modal)
      - ensures rel="noopener noreferrer"
      - optionally appends utm_source=<canonical host>

    Mutating the body invalidates Content-Length and ETag, so both are
    dropped and ConditionalGet (outer) does not falsely 304.
    """

    def process_response(self, request, response):
        config = _config(request)
        if not config.enable_external_link_handling:
            return response
        if response.status_code != 200 or not _is_html(response) or _is_admin(request.path):
            return response

        own_host = (config.canonical_origin or "").rstrip("/")
        own_netloc = urlsplit(own_host).netloc if own_host else ""
        if not own_netloc:
            return response

        source_param = "utm_source=" + own_netloc.split(":")[0].replace(".", "-")
        replacements = []

        content = response.content.decode("utf-8", errors="ignore")
        for match in ANCHOR_RE.finditer(content):
            tag = match.group(0)
            href_match = HREF_RE.search(tag)
            if not href_match:
                continue
            url = href_match.group(2)
            split = urlsplit(url)
            if not split.netloc or split.netloc.lower() == own_netloc.lower():
                continue
            if split.scheme not in ("http", "https"):
                continue
            new_tag = tag
            if "data-external" not in new_tag:
                new_tag = new_tag.replace("<a ", '<a data-external="true" ', 1)
            if "noopener" not in new_tag:
                rel_match = REL_RE.search(new_tag)
                if rel_match:
                    quote = rel_match.group(1)
                    merged = f'rel={quote}{rel_match.group(2)} noopener noreferrer{quote}'
                    new_tag = new_tag.replace(rel_match.group(0), merged, 1)
                else:
                    new_tag = new_tag[:-1] + ' rel="noopener noreferrer">'
            if config.external_link_utm and "utm_source" not in new_tag:
                sep = "&" if split.query else "?"
                quoted = href_match.group(0).replace(url, url + sep + source_param, 1)
                new_tag = new_tag.replace(href_match.group(0), quoted, 1)
            if new_tag != tag:
                replacements.append((tag, new_tag))

        if replacements:
            for old, new in replacements:
                content = content.replace(old, new, 1)
            response.content = content.encode("utf-8")
            response.headers.pop("Content-Length", None)
            response.headers.pop("ETag", None)
        return response


class LanguageFromURLMiddleware:
    """Optional bilingual mode: /de/... activates German, else default.

    Inert unless settings.ENABLE_BILINGUAL is True. Mirrors the gritsec
    pattern: no session write for anonymous visitors, Content-Language
    header set per response.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "ENABLE_BILINGUAL", False):
            return self.get_response(request)

        from django.utils import translation

        supported = {code for code, _name in getattr(settings, "LANGUAGES", [("en", "English")])}
        default = settings.LANGUAGE_CODE
        code = default
        path = request.path
        match = re.match(r"^/([a-z]{2}(?:-[a-zA-Z]{2})?)/", path)
        if match:
            candidate = match.group(1).lower().split("-")[0]
            if candidate in supported:
                code = candidate
        request.LANGUAGE_CODE = code
        translation.activate(code)
        try:
            response = self.get_response(request)
        except Exception:
            translation.deactivate()
            raise
        response.setdefault("Content-Language", code)
        translation.deactivate()
        return response
