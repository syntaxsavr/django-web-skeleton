"""URL routes for the core app."""

from django.urls import path, re_path

from core.views import articles as article_views
from core.views import auth as account_views
from core.views import twofa as twofa_views
from core.views import contact as contact_views
from core.views import fragments as fragment_views
from core.views import legal as legal_views
from core.views import machine as machine_views
from core.views import pages as page_views

urlpatterns = [
    path("", page_views.home, name="home"),
    path("demo/", page_views.demo, name="demo"),
    path("articles/", article_views.articles, name="articles"),
    path("articles/preview/", article_views.article_preview, name="article_preview"),
    path("articles/<slug:slug>/", article_views.article_detail, name="article_detail"),
    # --- Contact ---
    path("contact/", contact_views.contact, name="contact"),
    path("contact/thanks/", contact_views.contact_thanks, name="contact_thanks"),
    # --- Auth ---
    path("accounts/login/", account_views.RateLimitedLoginView.as_view(), name="login"),
    path("accounts/logout/", account_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", account_views.register, name="register"),
    path("accounts/register/confirm/", account_views.registration_otp, name="registration_otp"),
    path("accounts/register/resend/", account_views.registration_otp_resend, name="registration_otp_resend"),
    path(
        "accounts/password_reset/",
        account_views.PasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "accounts/password_reset/done/",
        account_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        account_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done/",
        account_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("account/", account_views.account_dashboard, name="account_dashboard"),
    path("account/two-factor/", twofa_views.two_factor_manage, name="two_factor_manage"),
    path("account/two-factor/setup/", twofa_views.two_factor_setup, name="two_factor_setup"),
    path("account/two-factor/verify/", twofa_views.two_factor_verify, name="two_factor_verify"),
    path("account/two-factor/remove/", twofa_views.two_factor_remove, name="two_factor_remove"),
    # --- Legal ---
    path("privacy/", legal_views.privacy, name="privacy"),
    path("imprint/", legal_views.imprint, name="imprint"),
    path("accessibility/", legal_views.accessibility, name="accessibility"),
    # --- Machine routes ---
    path("robots.txt", machine_views.robots_txt, name="robots_txt"),
    path("llms.txt", machine_views.llms_txt, name="llms_txt"),
    path("llms-full.txt", machine_views.llms_full_txt, name="llms_full_txt"),
    path("humans.txt", machine_views.humans_txt, name="humans_txt"),
    path("security.txt", machine_views.security_txt, name="security_txt"),
    path(".well-known/security.txt", machine_views.security_txt, name="security_txt_wellknown"),
    re_path(r"^([A-Za-z0-9-]{8,128})\.txt$", machine_views.indexnow_key_file, name="indexnow_key_file"),
    # --- Lazy sections ---
    path("lazy-section/<path:name>/", fragment_views.lazy_section, name="lazy_section"),
]
