"""Private file storage for sensitive downloads.

Files live outside MEDIA_ROOT in a directory that no URL route exposes.
The only path to an archive is the authenticated, ownership-checked
download view. This is defence in depth: the random file names are NOT
the protection.
"""

from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateMediaStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", str(getattr(settings, "PRIVATE_MEDIA_ROOT", Path("private_media"))))
        super().__init__(*args, **kwargs)
