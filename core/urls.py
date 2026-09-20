"""URL routes for the core app."""

from django.contrib.auth import views as auth_views
from django.urls import path, re_path
from django.views.generic import TemplateView

from core import views

urlpatterns = [
    path("", views.home, name="home"),
    path("demo/", views.demo, name="demo"),
    # --- Contact ---
    path("contact/", views.contact, name="contact"),
    path("contact/thanks/", views.contact_thanks, name="contact_thanks"),
    # --- Auth ---
    path("accounts/login/", views.RateLimitedLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", views.register, name="register"),
    path(
        "accounts/password_reset/",
        auth_views.PasswordResetView.as_view(template_name="core/account/password_reset.html"),
        name="password_reset",
    ),
    path(
        "accounts/password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="core/account/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="core/account/password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="core/account/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path("account/", views.account_dashboard, name="account_dashboard"),
    # --- Legal ---
    path("privacy/", TemplateView.as_view(template_name="core/legal/privacy.html"), name="privacy"),
    path("imprint/", TemplateView.as_view(template_name="core/legal/imprint.html"), name="imprint"),
    path(
        "accessibility/",
        TemplateView.as_view(template_name="core/legal/accessibility.html"),
        name="accessibility",
    ),
    # --- Machine routes ---
    path(
        "robots.txt",
        TemplateView.as_view(template_name="core/robots.txt", content_type="text/plain; charset=utf-8"),
        name="robots_txt",
    ),
    path("llms.txt", views.llms_txt, name="llms_txt"),
    path("llms-full.txt", views.llms_full_txt, name="llms_full_txt"),
    path(
        "humans.txt",
        TemplateView.as_view(template_name="core/humans.txt", content_type="text/plain; charset=utf-8"),
        name="humans_txt",
    ),
    path(
        "security.txt",
        TemplateView.as_view(template_name="core/security.txt", content_type="text/plain; charset=utf-8"),
        name="security_txt",
    ),
    path(
        ".well-known/security.txt",
        TemplateView.as_view(template_name="core/security.txt", content_type="text/plain; charset=utf-8"),
        name="security_txt_wellknown",
    ),
    re_path(r"^([A-Za-z0-9-]{8,128})\.txt$", views.indexnow_key_file, name="indexnow_key_file"),
    # --- Lazy sections ---
    path("lazy-section/<path:name>/", views.lazy_section, name="lazy_section"),
]
