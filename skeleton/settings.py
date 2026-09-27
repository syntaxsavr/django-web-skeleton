"""Settings for the django-skeleton project.

The debug/production switch
===========================

One flag decides everything: DJANGO_DEBUG (default True for development).

DEBUG=True:
    - verbose error pages
    - static/media served by runserver
    - console email backend
    - plain session/CSRF cookies (so dev tools and plain HTTP work)

DEBUG=False:
    - SECRET_KEY becomes mandatory (hard failure, no insecure fallback)
    - HSTS, SSL redirect, secure/proxied headers, secure cookies
    - SMTP email from environment

Everything feature-shaped (consent, tracking, SEO routes, middleware
switches, Turnstile, registration) lives in the SiteConfiguration
singleton and is editable in the admin control panel. Environment
variables can override the sensitive values (see core/models.py).
"""

import os
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Minimal .env loader: KEY=VALUE lines, no interpolation, no deps."""
    env_path = BASE_DIR / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("1", "true", "yes")

# Insecure placeholder allowed only in DEBUG. Production refuses to boot.
_SECRET = os.environ.get("DJANGO_SECRET_KEY", "")
if not _SECRET:
    if DEBUG:
        _SECRET = secrets.token_urlsafe(48)
    else:
        raise RuntimeError(
            "DJANGO_SECRET_KEY is required when DJANGO_DEBUG=False. "
            "Generate one: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
SECRET_KEY = _SECRET

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

if DEBUG:
    ALLOWED_HOSTS += ["0.0.0.0", "[::1]"]

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "core",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.ContentSecurityPolicyMiddleware",
    "core.middleware.SiteConfigurationMiddleware",
    "core.middleware.PersonalDataScraperBlockMiddleware",
    "core.middleware.SearchIndexingMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "core.middleware.LanguageFromURLMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "core.middleware.Staff2FAMiddleware",
    "accounts.middleware.AccountsMiddleware",
    "accounts.middleware.UserGateMiddleware",
    "core.middleware.ProtectedPageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.ExternalLinkMiddleware",
]

# Ordering rationale lives in AGENTS.md ("Middleware ordering"). Short
# version: config early (everything reads request.site_config), response
# rewriters (external links) last so they see the final HTML, gzip outside
# them so it compresses the rewritten bytes.

ROOT_URLCONF = "skeleton.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_settings",
                "core.context_processors.tracking_configuration",
            ],
        },
    },
]

WSGI_APPLICATION = "skeleton.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Argon2id first: the tightest mainstream password hashing. Existing
# PBKDF2 hashes upgrade transparently on the next login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/account/"
LOGOUT_REDIRECT_URL = "/"

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English")]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Flip to True (and extend LANGUAGES) to serve /<code>/ prefixed translations
# through core.middleware.LanguageFromURLMiddleware. See AGENTS.md.
ENABLE_BILINGUAL = False

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "core" / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "core.storage.MinifyingManifestStaticFilesStorage"},
}
# Manifest storage needs collectstatic; the test runner serves straight
# from source dirs instead.
if "test" in sys.argv:
    STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"
WHITENOISE_MAX_AGE = 60 * 60 * 24 * 28

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Email -----------------------------------------------------------------

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Provider presets: set EMAIL_PRESET and only add credentials. Any explicit
# EMAIL_HOST/PORT/TLS/SSL variable still wins over the preset.
EMAIL_PRESETS = {
    "ionos": {"EMAIL_HOST": "smtp.ionos.de", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
    "outlook": {"EMAIL_HOST": "smtp-mail.outlook.com", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
    "microsoft365": {"EMAIL_HOST": "smtp.office365.com", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
    "gmail": {"EMAIL_HOST": "smtp.gmail.com", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
    "posteo": {"EMAIL_HOST": "posteo.de", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
    "webde": {"EMAIL_HOST": "smtp.web.de", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
    "gmx": {"EMAIL_HOST": "mail.gmx.net", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
    "mailbox": {"EMAIL_HOST": "mailbox.org", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
    "mailgun": {"EMAIL_HOST": "smtp.mailgun.org", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
    "sendgrid": {"EMAIL_HOST": "smtp.sendgrid.net", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
    "brevo": {"EMAIL_HOST": "smtp-relay.brevo.com", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
    "strato": {"EMAIL_HOST": "smtp.strato.de", "EMAIL_PORT": "587", "EMAIL_USE_TLS": "True"},
}
preset = EMAIL_PRESETS.get(os.environ.get("EMAIL_PRESET", "").lower(), {})
EMAIL_HOST = os.environ.get("EMAIL_HOST", preset.get("EMAIL_HOST", ""))
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", preset.get("EMAIL_PORT", "587")))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", preset.get("EMAIL_USE_TLS", "True")).lower() in ("1", "true", "yes")
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False").lower() in ("1", "true", "yes")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "webmaster@localhost")
CONTACT_RECIPIENT_EMAIL = os.environ.get("CONTACT_RECIPIENT_EMAIL", "")

# --- Security: the production half of the switch ---------------------------

if not DEBUG:
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 180
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# Contact/quiz fetch() calls read the token from JS
CSRF_COOKIE_HTTPONLY = False
# CSRF failures render through the uniform error page (404 in production)
CSRF_FAILURE_VIEW = "core.views.errors.csrf_failure"

# --- Feature constants (values live in the admin control panel) ------------

# Environment overrides for sensitive values; empty = use the admin panel.
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")

# Staff must verify a TOTP second factor before reaching /admin/. Defaults
# to on whenever DEBUG is off; override explicitly for staging.
ENFORCE_STAFF_2FA = os.environ.get("ENFORCE_STAFF_2FA", str(not DEBUG)).lower() in (
    "1",
    "true",
    "yes",
)

# Article images upload as WebP when the control panel switch is on.
WEBP_QUALITY = int(os.environ.get("WEBP_QUALITY", "82"))

# Signed time-trap: forms must take at least this many seconds to fill.
CONTACT_MIN_SECONDS = int(os.environ.get("CONTACT_MIN_SECONDS", "3"))
CONTACT_RATE_LIMIT_SECONDS = int(os.environ.get("CONTACT_RATE_LIMIT_SECONDS", "300"))

# django-ratelimit windows for auth views (constant by design: brute force
# protection should not be accidentally disableable from the DB).
LOGIN_RATELIMIT = "10/m"
REGISTER_RATELIMIT = "3/m"
CODE_START_RATELIMIT = "5/15m"
CODE_VERIFY_RATELIMIT = "10/m"
TOKEN_REGISTER_RATELIMIT = "3/h"
CONTACT_IP_RATELIMIT = "5/h"

# Bootstrap seed credentials (manage.py seed). Seeding is a DEVELOPMENT
# convenience: the post-migrate signal only creates the superuser when
# DEBUG is on. Production must use createsuperuser, and refuses to boot
# while the password is unset or still the published development default.
SEED_ADMIN_USERNAME = os.environ.get("SEED_ADMIN_USERNAME", "admin")
SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "b_4sIcPW007")
SEED_ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com")
if not DEBUG and SEED_ADMIN_PASSWORD in ("", "b_4sIcPW007"):
    if "test" not in sys.argv:
        raise RuntimeError(
            "Refusing to run in production with the development seed password. "
            "Set SEED_ADMIN_PASSWORD to a strong unique value (or use DEBUG mode "
            "for local development)."
        )

# Sensitive downloads (data-export archives) live OUTSIDE MEDIA_ROOT and
# are never exposed by the /media/ route; only the authenticated view
# serves them.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

# Ops-file system (autonomous AI changes). Pending signed files are read
# from OPS_DIR/pending. Set OPS_SIGNING_KEY in production; in DEBUG a key
# derived from SECRET_KEY is used so local vibecoding needs no setup.
OPS_DIR = BASE_DIR / "ops"
OPS_SIGNING_KEY = os.environ.get("OPS_SIGNING_KEY", "")

# --- django-unfold admin theme ---------------------------------------------
# Light theme, brand-matched. Input contrast is enforced in core/css/admin.css
# (loaded only inside the admin via UNFOLD STYLES).
UNFOLD = {
    "SITE_TITLE": "Skeleton Admin",
    "SITE_HEADER": "django-skeleton",
    "SITE_SYMBOL": "page",
    "THEME": "light",
    "STYLES": ["/static/core/css/admin.css"],
    "SIDEBAR": {
        "show_search": True,
        "navigation": (
            {
                # Every on/off lives here, one focused page per domain, its
                # master switch at the top. The pages are proxy models over
                # the one SiteConfiguration row (core/models.py, bottom).
                "title": "Configuration",
                "separator": True,
                "items": (
                    {
                        "title": "Skeleton configuration",
                        "icon": "settings",
                        "link": "/admin/core/generalsettings/1/change/",
                        "badge": "core.admin.badge_config_changed",
                    },
                    {"title": "Header & navigation settings", "icon": "toolbar", "link": "/admin/core/headersettings/1/change/"},
                    {"title": "Footer settings", "icon": "call_to_action", "link": "/admin/core/footersettings/1/change/"},
                    {"title": "Articles settings", "icon": "article", "link": "/admin/core/articlessettings/1/change/"},
                    {"title": "SEO settings", "icon": "search", "link": "/admin/core/seosettings/1/change/"},
                    {"title": "Tracking & consent settings", "icon": "ads_click", "link": "/admin/core/trackingsettings/1/change/"},
                    {"title": "Contact form settings", "icon": "contact_mail", "link": "/admin/core/contactformsettings/1/change/"},
                    {"title": "Cloudflare Turnstile", "icon": "captcha", "link": "/admin/core/turnstilesettings/1/change/"},
                    {"title": "Stripe settings", "icon": "payment", "link": "/admin/core/stripesettings/1/change/"},
                    {"title": "Cal.com embed", "icon": "event", "link": "/admin/core/calcomsettings/1/change/"},
                    {"title": "Accounts & login settings", "icon": "group", "link": "/admin/core/accountssettings/1/change/"},
                    {"title": "Security & protection", "icon": "shield", "link": "/admin/core/protectionsettings/1/change/"},
                    {"title": "Privacy & retention (GDPR)", "icon": "auto_delete", "link": "/admin/core/retentionsettings/1/change/"},
                ),
            },
        ),
    },
}

# Sidebar groups (unfold renders these under the app sections). Keeping the
# group list here instead of per-model Meta keeps the admin overview in one
# place; every model still belongs to its app.
UNFOLD["SIDEBAR"]["navigation"] += (
    {
        "title": "Content",
        "separator": True,
        "items": (
            {"title": "Articles", "icon": "auto_stories", "link": "/admin/core/article/"},
            {"title": "Navigation items", "icon": "menu", "link": "/admin/core/navigationitem/"},
            {"title": "Footer sections", "icon": "table_rows", "link": "/admin/core/footersection/"},
            {"title": "Stripe buttons", "icon": "sell", "link": "/admin/core/stripebutton/"},
            {"title": "Robots rules", "icon": "bug_report", "link": "/admin/core/robotsrule/"},
        ),
    },
    {
        "title": "Communication",
        "separator": True,
        "items": (
            {
                "title": "Contact messages",
                "icon": "mail",
                "link": "/admin/core/contactmessage/",
                "badge": "core.admin.badge_contact_messages",
            },
        ),
    },
    {
        "title": "Access & protection",
        "separator": True,
        "items": (
            {"title": "Protected pages", "icon": "lock", "link": "/admin/core/protectedpage/"},
        ),
    },
    {
        "title": "Signup form",
        "separator": True,
        "items": (
            {"title": "Signup fields", "icon": "edit_note", "link": "/admin/accounts/registrationfield/"},
            {"title": "Consent texts", "icon": "fact_check", "link": "/admin/accounts/consenttext/"},
        ),
    },
    {
        "title": "Privacy",
        "separator": True,
        "items": (
            {"title": "Login traces", "icon": "fingerprint", "link": "/admin/accounts/loginevent/"},
            {"title": "Data export requests", "icon": "download", "link": "/admin/accounts/dataexportrequest/"},
            {"title": "Consent acceptances", "icon": "verified_user", "link": "/admin/accounts/userconsent/"},
        ),
    },
    {
        "title": "Autonomy",
        "separator": True,
        "items": (
            {"title": "How to change things", "icon": "auto_stories", "link": "/admin/docs/"},
            {"title": "Ops log", "icon": "history", "link": "/admin/core/opslog/"},
        ),
    },
)

# --- Logging ----------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"level": "WARNING"},
        "core": {"level": "INFO"},
    },
}
