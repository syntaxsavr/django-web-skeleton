"""Article index and published article detail views."""

from django.http import Http404
from django.shortcuts import get_object_or_404, render

from core.models import Article
from core.views.helpers import site_config


def articles(request):
    config = site_config(request)
    if not config.enable_articles:
        raise Http404
    entries = Article.objects.filter(published=True)
    return render(
        request,
        "core/articles.html",
        {
            "articles": entries,
            "featured_article": entries.filter(is_featured=True).first(),
            "page_title": "Articles",
            "meta_description": "Notes, guides and field reports from %s." % config.site_name,
        },
    )


def article_detail(request, slug):
    config = site_config(request)
    if not config.enable_articles:
        raise Http404
    article = get_object_or_404(Article.objects.prefetch_related("images"), slug=slug, published=True)
    return render(
        request,
        "core/article-detail.html",
        {
            "article": article,
            "page_title": article.seo_title or article.title,
            "meta_description": article.meta_description,
        },
    )
