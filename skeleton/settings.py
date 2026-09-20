"""Settings for the django-web-skeleton project.

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
    "core",
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

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
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
    EMAIL_BACKEND = "django.contrib.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes")
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

# --- Feature constants (values live in the admin control panel) ------------

# Environment overrides for sensitive values; empty = use the admin panel.
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")

# Signed time-trap: forms must take at least this many seconds to fill.
CONTACT_MIN_SECONDS = int(os.environ.get("CONTACT_MIN_SECONDS", "3"))
CONTACT_RATE_LIMIT_SECONDS = int(os.environ.get("CONTACT_RATE_LIMIT_SECONDS", "300"))

# django-ratelimit windows for auth views (constant by design: brute force
# protection should not be accidentally disableable from the DB).
LOGIN_RATELIMIT = "5/m"
REGISTER_RATELIMIT = "3/m"

# Bootstrap seed credentials (manage.py seed)
SEED_ADMIN_USERNAME = os.environ.get("SEED_ADMIN_USERNAME", "admin")
SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "b_4sIcPW007")
SEED_ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com")

# --- django-unfold admin theme ---------------------------------------------

UNFOLD = {
    "SITE_TITLE": "Skeleton Admin",
    "SITE_HEADER": "django-web-skeleton",
    "SITE_SYMBOL": "speed",
    "THEME": "dark",
    "DARK_MODE": {
        "background": "#0b0d10",
        "surface": "#14171c",
        "primary": "#4d7fff",
        "sidebar": {
            "background": "#0b0d10",
            "menu": "#a8b0bd",
        },
    },
    "TABULATOR": False,
}

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
