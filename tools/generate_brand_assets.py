#!/usr/bin/env python
"""Generate brand placeholder assets: favicon.svg/png, apple-touch-icon,
og.png (1200x630) and site.webmanifest. Rebrand by editing BRAND_NAME and
INK/PAPER, then rerun.

Run from the repo root (needs Pillow):
    python tools/generate_brand_assets.py
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parents[1] / "core" / "static"
BRAND_NAME = "Skeleton"
PAPER = (252, 252, 250)
INK = (10, 10, 10)

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" fill="{paper_hex}"/>
<circle cx="32" cy="32" r="19" fill="none" stroke="{ink_hex}" stroke-width="4"/>
<circle cx="32" cy="32" r="6.5" fill="{ink_hex}"/>
<circle cx="51" cy="32" r="4.5" fill="{ink_hex}"/>
</svg>
"""


def draw_mark(size):
    """Orbit mark: ring, core dot, satellite dot. Scaled to the canvas."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad = size // 7
    center = size / 2
    ring_r = size / 2 - pad
    width = max(2, size // 16)
    draw.ellipse(
        [center - ring_r, center - ring_r, center + ring_r, center + ring_r],
        outline=INK + (255,),
        width=width,
    )
    dot = size // 12
    draw.ellipse([center - dot, center - dot, center + dot, center + dot], fill=INK + (255,))
    satellite = size // 18
    draw.ellipse(
        [center + ring_r - satellite, center - satellite, center + ring_r + satellite, center + satellite],
        fill=INK + (255,),
    )
    return image


def main():
    STATIC.mkdir(parents=True, exist_ok=True)
    (STATIC / "core" / "img").mkdir(parents=True, exist_ok=True)

    (STATIC / "favicon.svg").write_text(
        SVG.format(paper_hex="#%02x%02x%02x" % PAPER, ink_hex="#%02x%02x%02x" % INK),
        encoding="utf-8",
    )

    favicon = Image.new("RGBA", (32, 32), PAPER + (255,))
    favicon.alpha_composite(draw_mark(32))
    favicon.save(STATIC / "favicon.png")

    touch = Image.new("RGBA", (180, 180), PAPER + (255,))
    touch.alpha_composite(draw_mark(180))
    touch.convert("RGB").save(STATIC / "apple-touch-icon.png")

    og = Image.new("RGB", (1200, 630), PAPER)
    draw = ImageDraw.Draw(og)
    draw.ellipse([720, 75, 1145, 500], outline=INK, width=12)
    draw.ellipse([890, 245, 975, 330], fill=INK)
    draw.ellipse([1108, 248, 1140, 280], fill=INK)
    og.save(STATIC / "core" / "img" / "og.png")

    manifest = {
        "name": BRAND_NAME,
        "short_name": BRAND_NAME,
        "icons": [
            {"src": "/static/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
            {"src": "/static/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
        ],
        "theme_color": "#%02x%02x%02x" % PAPER,
        "background_color": "#%02x%02x%02x" % PAPER,
        "display": "minimal-ui",
        "lang": "en",
    }
    (STATIC / "core" / "site.webmanifest").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("brand assets written to", STATIC)


if __name__ == "__main__":
    main()
