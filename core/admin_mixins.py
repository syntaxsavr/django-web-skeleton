"""Shared admin helpers: explanatory changelist banners.

Every ModelAdmin that mixes this in gets a description banner above the
changelist table explaining what the model is for, when you need it and
how it connects to other features. Written for the admins, and for any
coding agent wandering through the admin.
"""

from django.contrib import admin


class DescribedAdminMixin:
    """Set `changelist_description` on the ModelAdmin; the banner renders
    above the results (and above the empty-state message). Optionally set
    `changelist_preview_url` to render the public page in a live preview
    pane next to the list, so editors see the saved result immediately."""

    change_list_template = "admin/changelist_description.html"
    changelist_description = ""
    changelist_preview_url = ""

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(
            request,
            extra_context={
                "changelist_description": self.changelist_description,
                "changelist_preview_url": self.changelist_preview_url,
            },
        )


def described_fieldsets(description: str, fields) -> tuple:
    """One fieldset wrapping every field with an explanatory description,
    for add/change forms of simple models."""
    return ((None, {"description": description, "fields": fields}),)
