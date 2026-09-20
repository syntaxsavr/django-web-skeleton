"""Project error responses.

Security posture (production, DJANGO_DEBUG=False):

- Every error renders the SAME generic 404 page with status 404. Nothing
  else is ever displayed. A missing route, a forbidden path, a malformed
  request or a server fault are indistinguishable from the outside, so
  probing reveals neither existence, nor permissions, nor failure states.
- Each response carries a random padding string of random length
  (0-512 bytes). Constant content plus varying length destroys
  byte-length fingerprinting of error responses.

DEBUG mode keeps the real codes visible so developers can tell 403 from
500 while working.
"""

import secrets

from django.conf import settings
from django.shortcuts import render

_DISPLAY_CODE = 404


def error_padding() -> str:
    """Random string, random length 0-512 bytes. See module docstring."""
    length = secrets.randbelow(513)
    return secrets.token_hex((length + 1) // 2)[:length]


def _error_view(request, error_code):
    if getattr(settings, "DEBUG", False):
        return render(request, "core/404.html", {"error_code": error_code}, status=error_code)
    return render(
        request,
        "core/404.html",
        {"error_code": _DISPLAY_CODE, "padding": error_padding()},
        status=_DISPLAY_CODE,
    )


def handler400(request, exception=None):
    return _error_view(request, 400)


def handler403(request, exception=None):
    return _error_view(request, 403)


def handler404(request, exception=None):
    return _error_view(request, 404)


def csrf_failure(request, reason=""):
    """Uniform error rendering for CSRF failures (CSRF_FAILURE_VIEW)."""
    return _error_view(request, 403)


def handler500(request):
    if getattr(settings, "DEBUG", False):
        return render(request, "core/404.html", {"error_code": 500}, status=500)
    return render(
        request,
        "core/404.html",
        {"error_code": _DISPLAY_CODE, "padding": error_padding()},
        status=_DISPLAY_CODE,
    )
