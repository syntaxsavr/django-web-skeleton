# Design system

The skeleton ships a neutral, dark-first visual language designed to be
rebranded by changing tokens, not layouts. Adapted from the gritsec
(VETOSEC) design system.

## Character

Technical, calm, precise. The site is a tool, not a showroom: dark
surfaces, white text as the primary signal, one accent color, motion as
feedback rather than decoration. Never cyberpunk, never hacker theatre.

## Color tokens (`core/static/core/css/base.css`)

| Token | Value | Use |
|---|---|---|
| `--bg-page` / `--surface-0` | `#0b0d10` | page background |
| `--surface-1` | `#111419` | alternate section bands |
| `--surface-2` | `#171b21` | inputs, cards on dark |
| `--surface-3` | `#1e232b` | hover states |
| `--surface-card` | `#13171d` | card fill |
| `--text-primary` | `#f2f4f8` | body text |
| `--text-secondary` | `#a8b0bd` | leads, descriptions |
| `--text-faint` | `#6f7787` | metadata, footers |
| `--accent` | `#4d7fff` | interactive, focus, key highlights |
| `--accent-strong` | `#7aa0ff` | links on dark, hover |
| `--success` / `--danger` | `#20ad68` / `#d64545` | semantic states only |

Rules:

- The accent is a signal, not a surface. Never fill large areas with it.
- Green and red communicate state (success, danger). If the content does
  not genuinely express that state, do not use the color.
- White text carries meaning; gray text steps it down. Do not introduce
  more text colors.

Rebranding = change these values (plus `tools/generate_brand_assets.py`
for favicons/OG). The `a11y-light` class re-maps every token to a paper
edition; keep new components token-based so it keeps working.

## Type

Inter (self-hosted, OFL), weights 400/500/700. Fluid sizes with clamps:
`h1` from 2rem to 3.1rem, `h2` from 1.5rem to 2.1rem. Body 1rem, line
height 1.65. Monospace (system stack) for code, kickers and technical
labels. Letter spacing tightens as size grows (`-0.02em` on headings).

## Layout

- Content max width 1200px (`--container`), narrow reading 760px.
- Section padding `clamp(48px, 6vw, 88px)`, section gap up to 128px.
- Alternating bands: default background and `--surface-1` with 1px
  borders. A section communicates one idea.

## Motion grading

| Grade | Duration | Use |
|---|---|---|
| G0 | off | Reduced motion, print, `perf-lite` devices: static frames, no reveals |
| G1 | 120-220ms | Hover, focus, small UI feedback |
| G2 | 250-600ms | Section reveals, hero item entrances (stagger 45-110ms) |
| G3 | up to 900ms | Reserved for the single hero moment per page |

Easing: `cubic-bezier(0.22, 1, 0.36, 1)` for entrances. Animate only
opacity and transform (plus clip-path in the mask reveal). Everything
must respect `prefers-reduced-motion`, the a11y panel's reduce-motion
toggle, and the `perf-lite` class. Lottie parks on its final frame.

## Heroes

One per page. `min-height` from `clamp`, `data-hero-entrance`
choreography, optional Lottie stage with a fixed aspect ratio (zero
layout shift). The homepage hero is the only full-viewport moment.

## Accessibility

44px minimum interactive targets. Visible focus ring via
`--focus-ring`. Skip link on every page. Reveal animations never hide
content from assistive tech after settling. The footer panel offers
light mode, larger text (110/125%) and reduced motion, persisted in
localStorage under `skeleton.a11y`.

## Print

`print.css` repaints the dark site as clean A4 paper: chrome hidden,
orphans/widows protected, cards unbroken.
