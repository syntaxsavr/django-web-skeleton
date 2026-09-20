"""Image helper matching the skeleton's CLS discipline: every img gets
explicit dimensions, lazy loading and async decoding below the fold.

    {% lazy_img "core/img/example.png" width=600 height=400 alt="..." %}
    {% lazy_img "core/img/hero.png" width=1200 height=600 alt="..." eager=True %}
"""

from django import template
from django.templatetags.static import static
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def lazy_img(path, width, height, alt="", eager=False, cls=""):
    loading = "eager" if eager else "lazy"
    decoding = "sync" if eager else "async"
    class_attr = f' class="{cls}"' if cls else ""
    return mark_safe(
        f'<img src="{static(path)}" width="{width}" height="{height}" '
        f'alt="{alt}" loading="{loading}" decoding="{decoding}"{class_attr}>'
    )
