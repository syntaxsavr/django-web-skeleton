"""Legal and policy pages."""

from django.shortcuts import render


def privacy(request):
    return render(request, "core/legal/privacy.html", {"page_title": "Privacy"})


def imprint(request):
    return render(request, "core/legal/imprint.html", {"page_title": "Imprint"})


def accessibility(request):
    return render(request, "core/legal/accessibility.html", {"page_title": "Accessibility"})
