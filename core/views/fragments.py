"""Cached network-lazy template fragments."""

from django.http import Http404, HttpResponse
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods


def _fragment_names(name):
    clean = name.strip("/").replace("..", "")
    variants = (clean, clean.replace("-", "_"), clean.replace("_", "-"))
    unique = []
    for variant in variants:
        if variant and variant not in unique:
            unique.append("core/fragments/%s.html" % variant)
    return unique


def _cache_lazy_section(view_func):
    """Cache the fragment ONLY for anonymous visitors. Fragments are shared
    markup; if one ever reads request.user, the cached copy must not leak
    between users - so authenticated requests always render fresh."""
    cached = cache_page(60 * 60 * 12)(view_func)

    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        return cached(request, *args, **kwargs)

    return wrapper


@_cache_lazy_section
@require_http_methods(["GET"])
def lazy_section(request, name):
    for template_name in _fragment_names(name):
        try:
            return HttpResponse(render_to_string(template_name, request=request))
        except TemplateDoesNotExist:
            continue
    raise Http404("Unknown lazy section.")
