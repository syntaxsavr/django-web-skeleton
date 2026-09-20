"""Submit URLs to IndexNow (Bing, Yandex, Seznam).

    python manage.py indexnow                # all URLs from the live sitemap
    python manage.py indexnow --url=/demo/   # specific paths (repeatable)
    python manage.py indexnow --dry-run

The key lives in the control panel (SEO section). The <key>.txt proof
route is served by core.views.machine.indexnow_key_file and only ever matches
the configured key.
"""

import json
import re
import urllib.request
from urllib.parse import urljoin

from django.core.management.base import BaseCommand, CommandError

from core.models import SiteConfiguration

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
SITEMAP_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


class Command(BaseCommand):
    help = "Notify IndexNow of changed URLs."

    def add_arguments(self, parser):
        parser.add_argument("--url", action="append", default=[], help="Path or full URL; repeatable.")
        parser.add_argument("--dry-run", action="store_true", help="Print the payload instead of POSTing.")

    def handle(self, *args, **options):
        config = SiteConfiguration.get_solo()
        if not config.enable_indexnow:
            raise CommandError("IndexNow is disabled in the control panel (SEO section).")
        key = (config.indexnow_key or "").strip()
        if not key:
            raise CommandError("IndexNow key is empty. Set it in the control panel first.")

        host = config.canonical_origin.rstrip("/")
        key_location = urljoin(host + "/", key + ".txt")

        if options["url"]:
            urls = [u if u.startswith("http") else urljoin(host, u) for u in options["url"]]
        else:
            sitemap_url = urljoin(host + "/", "sitemap.xml")
            self.stdout.write(f"Reading {sitemap_url} ...")
            with urllib.request.urlopen(sitemap_url, timeout=30) as response:
                urls = SITEMAP_LOC_RE.findall(response.read().decode("utf-8"))

        if not urls:
            raise CommandError("No URLs found (empty sitemap or no --url given).")

        self.stdout.write(f"Verifying key file {key_location} ...")
        with urllib.request.urlopen(key_location, timeout=30) as response:
            served = response.read().decode("utf-8").strip()
        if served != key:
            raise CommandError("Key file does not match the configured key.")

        payload = {"host": host.split("//", 1)[1], "key": key, "keyLocation": key_location, "urlList": urls[:10000]}

        if options["dry_run"]:
            self.stdout.write(str(payload))
            return

        request = urllib.request.Request(
            INDEXNOW_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            self.stdout.write(self.style.SUCCESS(f"IndexNow responded HTTP {response.status} for {len(urls)} URL(s)."))
