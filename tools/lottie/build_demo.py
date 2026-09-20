#!/usr/bin/env python
"""Author the demo Lottie animation in pure Python.

Constraints (same discipline as the gritsec lottiekit): shape layers only,
no expressions, no effects, no text layers, no image assets. Anything this
script emits is safe for the light SVG renderer.

Run from the repo root:
    python tools/lottie/build_demo.py

Writes: core/static/core/lottie/hero-orbit.json
"""

import json
from pathlib import Path

W = H = 600
FPS = 30
DURATION = 3.0
FRAMES = int(FPS * DURATION)

ACCENT = [0.302, 0.498, 1.0]      # #4d7fff
ACCENT_SOFT = [0.302, 0.498, 1.0]
WHITE = [0.95, 0.96, 0.98]

EASE_OUT = {"i": {"x": [0.35], "y": [1]}, "o": {"x": [0.55], "y": [0]}}
EASE_IN_OUT = {"i": {"x": [0.42], "y": [0]}, "o": {"x": [0.58], "y": [1]}}


def keyframes(pairs, ease=EASE_OUT):
    """pairs: [(frame, value), ...] -> animated property"""
    keys = []
    for index, (frame, value) in enumerate(pairs):
        key = {"t": frame, "s": [value] if isinstance(value, (int, float)) else value}
        if 0 < index:
            key["i"] = ease["i"]
            key["o"] = ease["o"]
        keys.append(key)
    return {"a": 1, "k": keys}


def static(value):
    return {"a": 0, "k": value}


def stroke(color, width, opacity=100, dashed=False, offset=0):
    item = {
        "ty": "st",
        "c": static(color + [1]),
        "o": static(opacity),
        "w": static(width),
        "lc": 2,
        "lj": 2,
        "bm": 0,
        "nm": "stroke",
    }
    if dashed:
        item["d"] = [
            {"n": "d", "nm": "dash", "v": static(22)},
            {"n": "g", "nm": "gap", "v": static(16 + offset)},
        ]
    return item


def fill(color, opacity=100):
    return {"ty": "fl", "c": static(color + [1]), "o": static(opacity), "r": 1, "bm": 0, "nm": "fill"}


def ellipse(size, position=(0, 0)):
    return {"ty": "el", "p": static(list(position)), "s": static(list(size)), "d": 1, "nm": "ellipse"}


def transform(position=(0, 0), scale=(100, 100), rotation=None, opacity=None):
    tr = {
        "ty": "tr",
        "p": static(list(position) + [0]),
        "a": static([0, 0]),
        "s": static(list(scale)),
        "r": static(rotation or 0),
        "o": static(opacity if opacity is not None else 100),
        "sk": static(0),
        "sa": static(0),
    }
    return tr


def group(items, name="group"):
    return {"ty": "gr", "it": items + [transform()], "nm": name, "bm": 0}


def shape_layer(name, shapes, opacity=None, rotation=None, scale=None):
    return {
        "ddd": 0,
        "ind": 0,
        "ty": 4,
        "nm": name,
        "sr": 1,
        "ks": {
            "o": opacity or static(100),
            "r": rotation or static(0),
            "p": static([W / 2, H / 2, 0]),
            "a": static([0, 0, 0]),
            "s": scale or static([100, 100, 100]),
        },
        "ao": 0,
        "shapes": shapes,
        "ip": 0,
        "op": FRAMES,
        "st": 0,
        "bm": 0,
    }


def pulse_ring(size, color, delay):
    """A ring that expands from the core and fades out, staggered by delay."""
    period = FRAMES / 2
    start = delay
    mid = start + period * 0.6
    end = start + period
    ring = group(
        [
            ellipse((size, size)),
            stroke(color, 3, dashed=True),
        ]
    )
    ring["it"][-1]["s"] = keyframes([(start, 18), (end, 100)], EASE_OUT)
    layer = shape_layer("pulse-%d" % delay, [ring])
    layer["ks"]["o"] = keyframes([(start, 0), (start + 2, 55), (mid, 30), (end, 0)], EASE_OUT)
    layer["ip"] = 0
    layer["op"] = FRAMES
    return layer


def build():
    layers = []

    # Rotating dashed outer ring (the orbit path).
    outer = shape_layer(
        "outer-ring",
        [group([ellipse((430, 430)), stroke(ACCENT, 4, opacity=45, dashed=True)])],
    )
    outer["ks"]["r"] = keyframes([(0, 0), (FRAMES, 360)], EASE_IN_OUT)
    layers.append(outer)

    # Second ring, thinner, slower, opposite direction.
    inner = shape_layer(
        "inner-ring",
        [group([ellipse((300, 300)), stroke(ACCENT, 2, opacity=30)])],
    )
    inner["ks"]["r"] = keyframes([(0, 360), (FRAMES, 0)], EASE_IN_OUT)
    layers.append(inner)

    # Orbiting satellite: dot offset from center, layer rotation carries it.
    satellite = shape_layer(
        "satellite",
        [group([ellipse((26, 26), position=(215, 0)), fill(ACCENT)])],
    )
    satellite["ks"]["r"] = keyframes([(0, 0), (FRAMES, 360)], EASE_IN_OUT)
    layers.append(satellite)

    # Counter satellite on the inner ring, smaller, white.
    counter = shape_layer(
        "counter-satellite",
        [group([ellipse((14, 14), position=(150, 0)), fill(WHITE)])],
    )
    counter["ks"]["r"] = keyframes([(0, 360), (FRAMES, 0)], EASE_IN_OUT)
    layers.append(counter)

    # Expanding pulse rings, three of them, evenly staggered.
    layers.append(pulse_ring(420, ACCENT_SOFT, 0))
    layers.append(pulse_ring(420, ACCENT_SOFT, FRAMES / 3))
    layers.append(pulse_ring(420, ACCENT_SOFT, 2 * FRAMES / 3))

    # Core: filled dot with a breathing scale and a tight halo.
    core = shape_layer(
        "core",
        [
            group([ellipse((120, 120)), fill(ACCENT, opacity=12)]),
            group([ellipse((56, 56)), fill(ACCENT)]),
        ],
    )
    core["ks"]["s"] = keyframes(
        [(0, [100, 100, 100]), (FRAMES / 2, [108, 108, 100]), (FRAMES, [100, 100, 100])],
        EASE_IN_OUT,
    )
    layers.append(core)

    for index, layer in enumerate(layers):
        layer["ind"] = len(layers) - index

    return {
        "v": "5.7.4",
        "fr": FPS,
        "ip": 0,
        "op": FRAMES,
        "w": W,
        "h": H,
        "nm": "hero-orbit",
        "ddd": 0,
        "assets": [],
        "layers": layers,
        "markers": [],
    }


def main():
    out = Path(__file__).resolve().parents[2] / "core" / "static" / "core" / "lottie" / "hero-orbit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = build()
    out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(data['layers'])} layers)")


if __name__ == "__main__":
    main()
