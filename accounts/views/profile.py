"""Profile pages: dashboard, avatar, security (login trace), completion."""

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.authhelpers import pending_profile_gate
from accounts.forms import AvatarForm, ProfileDataForm
from accounts.models import LoginEvent, UserProfile
from core.views.helpers import site_config


@login_required
def account_dashboard(request):
    config = site_config(request)
    profile = UserProfile.for_user(request.user)
    new_token = request.session.pop("show_new_token", None)
    return render(
        request,
        "accounts/dashboard.html",
        {
            "page_title": "Your account",
            "profile": profile,
            "new_token": new_token,
            "missing_fields": profile.missing_required_fields(),
        },
    )


@login_required
def profile_settings(request):
    profile = UserProfile.for_user(request.user)
    config = site_config(request)
    if request.method == "POST":
        data_form = ProfileDataForm(request.POST, profile=profile)
        avatar_form = AvatarForm(request.POST, request.FILES)
        if data_form.is_valid() and avatar_form.is_valid():
            data_form.apply()
            avatar = avatar_form.cleaned_data.get("avatar")
            if avatar:
                _store_avatar(profile, avatar)
            elif request.POST.get("remove_avatar") and profile.avatar:
                profile.avatar.delete(save=False)
                profile.avatar = ""
                profile.save(update_fields=["avatar", "updated"])
            messages.success(request, "Profile saved.")
            return redirect("profile_settings")
    else:
        data_form = ProfileDataForm(profile=profile)
        avatar_form = AvatarForm()
    return render(
        request,
        "accounts/profile_settings.html",
        {
            "page_title": "Profile",
            "data_form": data_form,
            "avatar_form": avatar_form,
            "profile": profile,
            "allow_avatar": config.allow_avatar_upload,
        },
    )


def _store_avatar(profile, upload) -> None:
    """Re-encode: strips metadata, normalises size and format."""
    import io

    from PIL import Image, ImageOps
    from django.core.files.base import ContentFile

    image = Image.open(upload)
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGBA")
    image.thumbnail((256, 256))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    if profile.avatar:
        profile.avatar.delete(save=False)
    profile.avatar.save("avatar-%s.png" % profile.user_id, ContentFile(buffer.getvalue()), save=False)
    profile.save(update_fields=["avatar", "updated"])


@login_required
def profile_security(request):
    events = LoginEvent.objects.filter(user=request.user)
    paginator = Paginator(events, 20)
    page = paginator.get_page(request.GET.get("page"))
    from django_otp import devices_for_user

    devices = [d for d in devices_for_user(request.user) if d.confirmed]
    return render(
        request,
        "accounts/profile_security.html",
        {
            "page_title": "Sign-in history",
            "events": page,
            "devices": devices,
        },
    )


@login_required
def account_complete(request):
    profile = UserProfile.for_user(request.user)
    if not profile.missing_required_fields():
        return redirect("account_dashboard")
    if request.method == "POST":
        form = ProfileDataForm(request.POST, profile=profile, only_missing=True)
        if form.is_valid():
            form.apply()
            gate = pending_profile_gate(request, request.user)
            if gate:
                return gate
            messages.success(request, "Thanks! Your profile is complete.")
            return redirect("account_dashboard")
    else:
        form = ProfileDataForm(profile=profile, only_missing=True)
    return render(
        request,
        "accounts/complete_profile.html",
        {"page_title": "Complete your profile", "form": form},
    )
