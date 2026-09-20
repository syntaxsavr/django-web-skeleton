# Design system

Paper and ink. The skeleton ships a white-page editorial system where
typography is the design: one giant display letter, small sentences, hair
line rules, no rounded corners, no gradients. Adapted from the gritsec
(VETOSEC) design discipline but inverted for paper.

## Character

Authored, typographic, calm. The page reads like a printed spec sheet or
dictionary entry: black text on white, scale contrast instead of color
contrast, motion as feedback rather than decoration. Avoid the usual
template tells: no centered-everything hero, no gradient blobs, no rounded
card grids, no em dashes in copy.

## Color tokens (`core/static/core/css/base.css`)

| Token | Value | Use |
|---|---|---|
| `--paper` | `#fcfcfa` | page background |
| `--ink` | `#0a0a0a` | text, rules, buttons |
| `--ink-60` | `#575752` | leads, descriptions |
| `--ink-40` | `#8a8a84` | metadata, indexes |
| `--rule` | `rgba(10,10,10,.16)` | hairlines |
| `--rule-strong` | `#0a0a0a` | section rules, borders |
| `--wash` | `#f3f3ee` | subtle fills, code chips |

Rules:

- Black and white carry the design. There is no accent color; emphasis
  comes from scale, weight and the Instrument Serif italic.
- Errors are the only red (`#a02121`). Use it for genuine errors only.
- The `theme-dark` class (footer toggle) inverts the tokens. New
  components must stay token-based or the inversion breaks.

## Type

Two families, both OFL, self-hosted in `core/static/core/font/`:

- **Space Grotesk** (variable 300 to 700): everything structural.
  Headings at weight 500, tight tracking (-0.035em), line-height 1.02.
- **Instrument Serif** (regular + italic): editorial accents inside
  headings via `.serif-em`, and full sentences that need a softer voice
  (error-page headings).

Micro-labels and UI chrome use the system mono stack (`.mono-label`):
0.72rem, uppercase, 0.16em tracking. Scale contrast is the identity: the
home hero pairs a letter of up to 22rem with 1.2rem sentences.

## Layout

- Content max width 1240px, narrow reading 720px.
- Section rules: full-width 1px `--rule-strong` top borders between
  blocks. A section communicates one idea.
- Listing things: `.rule-rows` / `.rule-row` (index number, title, text)
  replaces cards. Borders, not boxes.
- Corner radius is zero everywhere (enforced globally).

## Heroes

One per page, editorial by construction: a giant glyph or word plus small
copy that leans on it (see the home page: one big D, two sentences
starting with d, a noun marker superscript). `data-hero-entrance`
sequences the items.

## Motion grading

| Grade | Duration | Use |
|---|---|---|
| G0 | off | Reduced motion, print, `perf-lite` devices: static frames, no reveals |
| G1 | 120-220ms | Hover, focus, small UI feedback |
| G2 | 250-600ms | Section reveals, hero item entrances (stagger 45-110ms) |
| G3 | up to 900ms | Reserved for the single hero moment per page |

Easing: `cubic-bezier(0.22, 1, 0.36, 1)` for entrances. Animate only
opacity and transform (plus clip-path in the mask reveal). Everything
must respect `prefers-reduced-motion` and the footer reduce-motion
toggle. Lottie parks on its final frame; the ink orbit animation pauses
offscreen.

## Accessibility

44px minimum interactive targets. Visible focus: 2px black ring offset
on paper. Skip link on every page. The footer Display column offers
dark mode, larger text (110/125%), reduced motion and print, persisted
in localStorage under `skeleton.a11y`.

## Print

The site is already paper; `print.css` only removes chrome (header,
footer, buttons, Lottie) and protects page breaks.
