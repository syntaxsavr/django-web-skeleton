"""Media helpers: automatic WebP conversion and external video embeds."""

import logging
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image

logger = logging.getLogger(__name__)

CONVERTIBLE_EXTENSIONS = (".jpg", ".jpeg", ".png")


def webp_enabled() -> bool:
    from core.models import SiteConfiguration

    return SiteConfiguration.get_solo().enable_webp_conversion


def auto_webp(instance, field_name: str) -> bool:
    """Convert an ImageFieldFile to WebP in place when the control panel
    asks for it. Runs after super().save() (the file is stored by then).
    Returns True when the field was replaced."""
    field_file = getattr(instance, field_name)
    if not field_file:
        return False
    name = field_file.name
    if not name.lower().endswith(CONVERTIBLE_EXTENSIONS):
        return False
    if not webp_enabled():
        return False
    try:
        image = Image.open(field_file.path)
        image.load()
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")
        webp_name = name.rsplit(".", 1)[0] + ".webp"
        buffer = BytesIO()
        image.save(buffer, format="WEBP", quality=getattr(settings, "WEBP_QUALITY", 82))
        storage, old_name = field_file.storage, name
        field_file.save(webp_name, ContentFile(buffer.getvalue()), save=False)
        instance.save(update_fields=[field_name])
        if old_name != getattr(instance, field_name).name:
            storage.delete(old_name)
        return True
    except Exception:
        logger.exception("WebP conversion failed for %s", name)
        return False


def video_embed_parts(url: str):
    """Classify an external video URL. Returns (provider, embed_url) with
    ("", "") for anything that is not a recognized YouTube or Vimeo URL."""
    url = (url or "").strip()
    if not url:
        return "", ""
    lower = url.lower()
    if "youtube.com/watch" in lower or "youtu.be/" in lower or "youtube.com/shorts/" in lower or "youtube.com/embed/" in lower:
        video_id = ""
        if "youtu.be/" in lower:
            video_id = url.split("youtu.be/", 1)[1]
        elif "watch" in lower and "v=" in lower:
            video_id = url.split("v=", 1)[1].split("&", 1)[0]
        elif "shorts/" in lower:
            video_id = url.split("shorts/", 1)[1]
        elif "embed/" in lower:
            video_id = url.split("embed/", 1)[1]
        video_id = video_id.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
        if video_id:
            return "youtube", f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0"
    if "vimeo.com/" in lower:
        tail = url.split("vimeo.com/", 1)[1].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
        if tail.isdigit():
            return "vimeo", f"https://player.vimeo.com/video/{tail}"
    return "", ""
