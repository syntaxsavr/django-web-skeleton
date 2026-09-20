"""Static files storage that minifies CSS and JS during collectstatic.

Django's post-processing hashes file content read from the SOURCE storage
(paths maps name -> (storage, path) of the original finder file), not from
the collected copy in STATIC_ROOT. Minifying only the collected copy would
leave every hashed file unminified. So this storage:

1. wraps the source storages so `_post_process` reads minified bytes
   (hashed files and their brotli/gzip siblings are minified), and
2. minifies the plain, unhashed copies in STATIC_ROOT as well.

Vendor files and *.min.* files are skipped; they ship pre-minified.
Public output therefore carries no source comments.
Maintained by syntaxsavr.
"""

from django.core.files.base import ContentFile

import rcssmin
import rjsmin
from whitenoise.storage import CompressedManifestStaticFilesStorage


class MinifyingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Minify .css and .js during collectstatic, then hash and compress."""

    minifiers = {
        ".css": rcssmin.cssmin,
        ".js": rjsmin.jsmin,
    }

    skip_suffixes = (".min.css", ".min.js")
    skip_fragments = ("/vendor/",)

    def _should_minify(self, name: str) -> bool:
        lowered = name.lower()
        if lowered.endswith(self.skip_suffixes):
            return False
        return not any(fragment in lowered for fragment in self.skip_fragments)

    def _minified(self, name: str, raw: bytes):
        for suffix, minify in self.minifiers.items():
            if name.lower().endswith(suffix):
                try:
                    return minify(raw.decode("utf-8")).encode("utf-8")
                except Exception:
                    return raw
        return raw

    def _minify_collected(self, paths):
        for name in paths:
            if not self._should_minify(name):
                continue
            path = self.path(name)
            try:
                with open(path, "rb") as handle:
                    raw = handle.read()
            except OSError:
                continue
            minified = self._minified(name, raw)
            if minified != raw:
                with open(path, "wb") as handle:
                    handle.write(minified)

    class _MinifyingSourceStorage:
        """Duck-typed wrapper: open() returns a minified ContentFile."""

        def __init__(self, storage, owner):
            self._storage = storage
            self._owner = owner

        def open(self, path):
            original = self._storage.open(path)
            if not self._owner._should_minify(path):
                return original
            minified = self._owner._minified(path, original.read())
            original.close()
            return ContentFile(minified)

    def post_process(self, paths, dry_run=False, **options):
        if not dry_run:
            self._minify_collected(paths)
            wrapped = {}
            for name, entry in paths.items():
                storage, path = entry
                wrapped[name] = (self._MinifyingSourceStorage(storage, self), path)
            paths = wrapped
        yield from super().post_process(paths, dry_run=dry_run, **options)
