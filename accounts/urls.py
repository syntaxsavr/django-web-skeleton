"""Account-space routes under /accounts/ and /account/."""

from django.urls import path

from accounts.views import auth as auth_views
from accounts.views import gdpr as gdpr_views
from accounts.views import profile as profile_views

urlpatterns = [
    # --- login methods ---
    path("accounts/login/", auth_views.login_view, name="login"),
    path("accounts/login/code/", auth_views.login_code_start, name="login_code_start"),
    path("accounts/login/code/verify/", auth_views.login_code_verify, name="login_code_verify"),
    path("accounts/login/magic/", auth_views.login_magic_start, name="login_magic_start"),
    path("accounts/login/magic/<str:token>/", auth_views.login_magic_click, name="login_magic_click"),
    path("accounts/login/token/", auth_views.login_token, name="login_token"),
    path("accounts/login/token/new/", auth_views.token_register, name="token_register"),
    # --- registration ---
    path("accounts/register/", auth_views.register, name="register"),
    # --- account space ---
    path("account/", profile_views.account_dashboard, name="account_dashboard"),
    path("account/profile/", profile_views.profile_settings, name="profile_settings"),
    path("account/security/", profile_views.profile_security, name="profile_security"),
    path("account/complete/", profile_views.account_complete, name="account_complete"),
    path("account/privacy/", gdpr_views.privacy_center, name="privacy_center"),
    path("account/privacy/export/", gdpr_views.export_request, name="export_request"),
    path("account/privacy/export/<int:pk>/download/", gdpr_views.export_download, name="export_download"),
    path("account/privacy/delete-data/", gdpr_views.data_deletion, name="data_deletion"),
    path("account/privacy/delete-account/", gdpr_views.account_deletion, name="account_deletion"),
]
