#!/usr/bin/env python
"""Generate brand placeholder assets: favicon.svg/png, apple-touch-icon,
og.png (1200x630) and site.webmanifest. Rebrand by editing BRAND_NAME and
the two accent colors, then rerun.

Run from the repo root (needs Pillow):
    python tools/generate_brand_assets.py
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parents[2] / "core" / "static"
BRAND_NAME = "Skeleton"
BG = (11, 13, 16)
ACCENT = (77, 127, 255)

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="{bg_hex}"/>
<circle cx="32" cy="32" r="17" fill="none" stroke="{accent_hex}" stroke-width="4" stroke-dasharray="12 7"/>
<circle cx="32" cy="32" r="6.5" fill="{accent_hex}"/>
<circle cx="49" cy="32" r="4" fill="#f2f4f8"/>
</svg>
"""


def rounded(draw, box, radius, color):
    draw.rounded_rectangle(box, radius=radius, fill=color)


def draw_mark(size):
    """Shield-free orbit mark, scaled to the given canvas."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad = size // 8
    center = size / 2
    ring_r = size / 2 - pad
    width = max(2, size // 16)
    draw.ellipse(
        [center - ring_r, center - ring_r, center + ring_r, center + ring_r],
        outline=ACCENT + (255,),
        width=width,
    )
    dot = size // 12
    draw.ellipse([center - dot, center - dot, center + dot, center + dot], fill=ACCENT + (255,))
    satellite = size // 20
    draw.ellipse(
        [center + ring_r - satellite, center - satellite, center + ring_r + satellite, center + satellite],
        fill=(242, 244, 248, 255),
    )
    return image


def main():
    STATIC.mkdir(parents=True, exist_ok=True)
    (STATIC / "core" / "img").mkdir(parents=True, exist_ok=True)

    (STATIC / "favicon.svg").write_text(
        SVG.format(bg_hex="#%02x%02x%02x" % BG, accent_hex="#%02x%02x%02x" % ACCENT),
        encoding="utf-8",
    )

    favicon = Image.new("RGBA", (32, 32), BG + (255,))
    rounded(ImageDraw.Draw(favicon), [0, 0, 32, 32], 7, BG + (255,))
    mark = draw_mark(32)
    favicon.alpha_composite(mark)
    favicon.save(STATIC / "favicon.png")

    touch = Image.new("RGBA", (180, 180), BG + (255,))
    rounded(ImageDraw.Draw(touch), [0, 0, 180, 180], 40, BG + (255,))
    touch.alpha_composite(draw_mark(180), (0, 0))
    touch.convert("RGB").save(STATIC / "apple-touch-icon.png")

    og = Image.new("RGB", (1200, 630), BG)
    draw = ImageDraw.Draw(og)
    draw.ellipse([760, 90, 1130, 460], outline=ACCENT, width=10)
    draw.ellipse([925, 235, 965, 275], fill=ACCENT)
    draw.ellipse([1105, 235, 1125, 255], fill=(242, 244, 248))
    og.save(STATIC / "core" / "img" / "og.png")

    manifest = {
        "name": BRAND_NAME,
        "short_name": BRAND_NAME,
        "icons": [
            {"src": "/static/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
            {"src": "/static/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
        ],
        "theme_color": "#%02x%02x%02x" % BG,
        "background_color": "#%02x%02x%02x" % BG,
        "display": "minimal-ui",
        "lang": "en",
    }
    (STATIC / "core" / "site.webmanifest").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("brand assets written to", STATIC)


if __name__ == "__main__":
    main()
