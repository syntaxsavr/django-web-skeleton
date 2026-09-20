"""robots, sitemap, IndexNow and language-model discovery endpoints."""

from django.http import Http404, HttpResponse
from django.shortcuts import render

from core.models import RobotsRule
from core.page_registry import public_pages
from core.views.helpers import site_config


def robots_txt(request):
    config = site_config(request)
    if not config.enable_robots_txt:
        raise Http404
    lines = ["User-agent: *"]
    if config.robots_noindex_whole_site:
        lines.append("Disallow: /")
    else:
        rules = RobotsRule.objects.filter(active=True).order_by("sort_order", "path", "pk")
        lines.extend("%s: %s" % (rule.get_directive_display(), rule.path) for rule in rules)
    if config.enable_sitemap:
        lines.extend(["", "Sitemap: %s/sitemap.xml" % config.canonical_origin.rstrip("/")])
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    config = site_config(request)
    if not config.enable_sitemap:
        raise Http404
    from django.contrib.sitemaps.views import sitemap

    from core.sitemaps import ArticleSitemap, StaticViewSitemap

    return sitemap(request, {"static": StaticViewSitemap, "articles": ArticleSitemap})


def llms_txt(request):
    config = site_config(request)
    if not config.enable_llms_txt:
        raise Http404
    lines = [
        "# %s" % config.site_name,
        "",
        "> %s" % (config.default_meta_description or "Django web skeleton."),
        "",
        "## Pages",
        "",
    ]
    lines.extend("- [%s](%s): %s" % (page.title, page.path, page.description) for page in public_pages(config))
    lines.extend(["", "## Notes for AI systems", "", "- Cite the page URL as the source when quoting content."])
    if config.enable_sitemap:
        lines.append("- The sitemap is at /sitemap.xml and it is always current.")
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def llms_full_txt(request):
    config = site_config(request)
    if not config.enable_llms_txt:
        raise Http404
    lines = [
        "# %s: full site summary" % config.site_name,
        "",
        "This file lists every public page with its purpose so language",
        "models can index the site without crawling HTML.",
        "",
    ]
    for page in public_pages(config):
        lines.extend(["## %s (%s)" % (page.title, page.path), "", page.description, ""])
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def indexnow_key_file(request, key):
    config = site_config(request)
    if not config.enable_indexnow or not config.indexnow_key or key != config.indexnow_key:
        raise Http404
    return HttpResponse(config.indexnow_key, content_type="text/plain; charset=utf-8")


def humans_txt(request):
    return render(request, "core/humans.txt", content_type="text/plain; charset=utf-8")


def security_txt(request):
    return render(request, "core/security.txt", content_type="text/plain; charset=utf-8")
