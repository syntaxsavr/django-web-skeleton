#!/usr/bin/env python
"""Author the demo Lottie animation in pure Python.

Constraints (same discipline as the gritsec lottiekit): shape layers only,
no expressions, no effects, no text layers, no image assets. The output
uses only constructs the light SVG renderer handles identically to full
lottie-web: static ellipse shapes, layer rotation/opacity/scale keyframes
with three-component scale values, easing on every keyframe except the last.

Run from the repo root:
    python tools/lottie/build_demo.py

Writes: core/static/core/lottie/hero-orbit.json
"""

import json
from pathlib import Path

W = H = 600
FPS = 30
DURATION = 4.0
FRAMES = int(FPS * DURATION)

INK = [0.06, 0.06, 0.06]
PAPER = [1.0, 1.0, 1.0]

EASE = {"i": {"x": [0.42], "y": [0]}, "o": {"x": [0.58], "y": [1]}}


def keyframes(pairs):
    """pairs: [(frame, value), ...]. The value must already be the final
    "s" payload (list for scale/position, single-element list for scalars).
    Every keyframe except the last carries easing for its outgoing segment."""
    keys = []
    for index, (frame, value) in enumerate(pairs):
        key = {"t": frame, "s": value}
        if index < len(pairs) - 1:
            key["i"] = EASE["i"]
            key["o"] = EASE["o"]
        keys.append(key)
    return {"a": 1, "k": keys}


def static(value):
    return {"a": 0, "k": value}


def stroke(color, width, opacity=100):
    return {
        "ty": "st",
        "c": static(color + [1]),
        "o": static(opacity),
        "w": static(width),
        "lc": 2,
        "lj": 2,
        "bm": 0,
        "nm": "stroke",
    }


def fill(color, opacity=100):
    return {"ty": "fl", "c": static(color + [1]), "o": static(opacity), "r": 1, "bm": 0, "nm": "fill"}


def ellipse(size, position=(0, 0)):
    return {"ty": "el", "p": static(list(position)), "s": static([size, size]), "d": 1, "nm": "ellipse"}


def transform(position=(0, 0), scale=(100, 100), rotation=0, opacity=100):
    return {
        "ty": "tr",
        "p": static(list(position) + [0]),
        "a": static([0, 0]),
        "s": static([scale[0], scale[1], 100]),
        "r": static(rotation),
        "o": static(opacity),
        "sk": static(0),
        "sa": static(0),
    }


def group(items, name="group"):
    return {"ty": "gr", "it": items + [transform()], "nm": name, "bm": 0}


def shape_layer(name, shapes, *, rotation=None, opacity=None, scale=None, ind=0):
    ks = {
        "o": opacity if opacity is not None else static(100),
        "r": rotation if rotation is not None else static(0),
        "p": static([W / 2, H / 2, 0]),
        "a": static([0, 0, 0]),
        "s": scale if scale is not None else static([100, 100, 100]),
    }
    return {
        "ddd": 0,
        "ind": ind,
        "ty": 4,
        "nm": name,
        "sr": 1,
        "ks": ks,
        "ao": 0,
        "shapes": shapes,
        "ip": 0,
        "op": FRAMES,
        "st": 0,
        "bm": 0,
    }


def rotating_ring(size, width, opacity, start, end, ind):
    return shape_layer(
        "ring-%d" % ind,
        [group([ellipse(size), stroke(INK, width, opacity=opacity)])],
        rotation=keyframes([(0, [start]), (FRAMES, [end])]),
        ind=ind,
    )


def orbiting_dot(radius, size, filled, start, end, ind):
    dot = ellipse(size, position=(radius, 0))
    shape = fill(INK) if filled else stroke(INK, 2)
    return shape_layer(
        "dot-%d" % ind,
        [group([dot, shape])],
        rotation=keyframes([(0, [start]), (FRAMES, [end])]),
        ind=ind,
    )


def pulse_ring(delay, ind):
    """Ring that grows from the core and fades: layer scale + opacity."""
    return shape_layer(
        "pulse-%d" % ind,
        [group([ellipse(420), stroke(INK, 2, opacity=100)])],
        scale=keyframes(
            [(delay, [30, 30, 100]), (delay + FRAMES // 2, [115, 115, 100])],
        ),
        opacity=keyframes(
            [(delay, [0]), (delay + 8, [45]), (delay + FRAMES // 2, [0])],
        ),
        ind=ind,
    )


def build():
    half = FRAMES // 2
    layers = [
        rotating_ring(430, 3, 100, 0, 360, 1),
        rotating_ring(275, 1.5, 35, 360, 0, 2),
        orbiting_dot(215, 24, True, 0, 360, 3),
        orbiting_dot(137, 14, False, 360, 0, 4),
        pulse_ring(0, 5),
        pulse_ring(half, 6),
        shape_layer(
            "core",
            [group([ellipse(54), fill(INK)])],
            ind=7,
        ),
    ]
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
