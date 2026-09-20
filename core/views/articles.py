"""Article index, detail and live editor preview views."""

from types import SimpleNamespace

from django.contrib.admin.views.decorators import staff_member_required
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
    print("VDEBUG enable_articles:", config.enable_articles, "slugs:", list(Article.objects.values_list("slug", "published")))
    article = get_object_or_404(Article.objects.prefetch_related("images", "blocks"), slug=slug, published=True)
    return render(
        request,
        "core/article-detail.html",
        {
            "article": article,
            "blocks": article.blocks.all(),
            "page_title": article.seo_title or article.title,
            "meta_description": article.meta_description,
        },
    )


def _preview_block(index, data):
    """Shape one submitted inline row into the attributes the template uses."""

    class _Image:
        def __init__(self, image):
            self._image = image

        @property
        def url(self):
            return self._image.image.url if self._image else ""

        @property
        def alt_text(self):
            return self._image.alt_text if self._image else ""

        @property
        def caption(self):
            return self._image.caption if self._image else ""

        @property
        def credit(self):
            return self._image.credit if self._image else ""

    image = data.get("image")
    buy = data.get("buy_button")
    url = data.get("video_url", "")
    from core.mediatools import video_embed_parts

    provider, embed = video_embed_parts(url)
    video_file = data.get("video_file")
    return SimpleNamespace(
        kind=data.get("kind", "text"),
        heading_level=data.get("heading_level") or "2",
        text=data.get("text", ""),
        quote_attribution=data.get("quote_attribution", ""),
        image=_Image(image) if image else None,
        has_video_file=bool(video_file),
        video_provider=provider,
        video_embed_url=embed,
        external_video=bool(provider),
        video_caption=data.get("video_caption", ""),
        buy_button=buy,
    )


@staff_member_required
def article_preview(request):
    """Render the article as the editor currently sees it: the change form
    is POSTed here unchanged and rebuilt without touching the database."""
    if request.method != "POST":
        raise Http404
    config = site_config(request)
    if not config.enable_articles and not request.user.is_staff:
        raise Http404

    def _get(name, default=""):
        return request.POST.get(name, default)

    try:
        article = Article.objects.get(pk=_get("pk") or 0)
    except (Article.DoesNotExist, ValueError):
        article = None

    prefix = _get("inline_prefix", "blocks")
    try:
        total = int(request.POST.get(f"{prefix}-TOTAL_FORMS", "0"))
    except ValueError:
        total = 0

    from core.models import ArticleImage, StripeButton

    blocks = []
    for i in range(total):
        data = {
            "kind": _get(f"{prefix}-{i}-kind", "text"),
            "heading_level": _get(f"{prefix}-{i}-heading_level"),
            "text": _get(f"{prefix}-{i}-text"),
            "quote_attribution": _get(f"{prefix}-{i}-quote_attribution"),
            "video_url": _get(f"{prefix}-{i}-video_url"),
            "video_caption": _get(f"{prefix}-{i}-video_caption"),
            "image": ArticleImage.objects.filter(pk=_get(f"{prefix}-{i}-image") or 0).first(),
            "buy_button": StripeButton.objects.filter(pk=_get(f"{prefix}-{i}-buy_button") or 0).first(),
        }
        upload = request.FILES.get(f"{prefix}-{i}-video_file")
        data["video_file"] = upload
        blocks.append(_preview_block(i, data))

    if article is None:
        article = SimpleNamespace(
            title=_get("title", "Untitled preview"),
            excerpt=_get("excerpt"),
            content=_get("content"),
            author_name=_get("author_name", "Editorial team"),
            category=_get("category"),
            hero_image=None,
            hero_image_alt="",
            hero_image_caption="",
            hero_image_credit="",
            show_disclaimer=_get("show_disclaimer") == "on",
            show_ai_disclosure=_get("show_ai_disclosure") == "on",
            published_at=None,
        )
    else:
        preview = SimpleNamespace(**{f: getattr(article, f) for f in (
            "title", "excerpt", "content", "author_name", "category", "hero_image",
            "hero_image_alt", "hero_image_caption", "hero_image_credit",
            "show_disclaimer", "show_ai_disclosure", "published_at",
        )})
        # posted overrides win so the preview matches the editor state
        for field in ("title", "excerpt", "content", "author_name", "category"):
            posted = _get(field)
            if posted:
                setattr(preview, field, posted)
        preview.show_disclaimer = _get("show_disclaimer") == "on"
        preview.show_ai_disclosure = _get("show_ai_disclosure") == "on"
        article = preview

    return render(
        request,
        "core/article-detail.html",
        {
            "article": article,
            "blocks": blocks,
            "is_preview": True,
            "page_title": (article.title or "Preview") + " (preview)",
        },
    )
