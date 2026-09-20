"""Project error responses."""

from django.shortcuts import render


def _error_view(request, error_code):
    return render(request, "core/404.html", {"error_code": error_code}, status=error_code)


def handler400(request, exception=None):
    return _error_view(request, 400)


def handler403(request, exception=None):
    return _error_view(request, 403)


def handler404(request, exception=None):
    return _error_view(request, 404)


def handler500(request):
    return _error_view(request, 500)
