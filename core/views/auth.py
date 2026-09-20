"""Authentication, registration and account views."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from core.forms import RegistrationForm
from core.views.helpers import site_config


def _too_many_requests(request):
    return render(request, "core/404.html", {"error_code": 429}, status=429)


class RateLimitedLoginView(auth_views.LoginView):
    template_name = "core/account/login.html"
    redirect_authenticated_user = True

    @method_decorator(ratelimit(key="ip", rate=settings.LOGIN_RATELIMIT, block=False))
    def dispatch(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            return _too_many_requests(request)
        return super().dispatch(request, *args, **kwargs)


class LogoutView(auth_views.LogoutView):
    pass


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "core/account/password_reset.html"


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "core/account/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "core/account/password_reset_confirm.html"


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "core/account/password_reset_complete.html"


@ratelimit(key="ip", rate=settings.REGISTER_RATELIMIT, block=False)
def register(request):
    config = site_config(request)
    if getattr(request, "limited", False):
        return _too_many_requests(request)
    if not config.enable_public_registration:
        raise Http404
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
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
