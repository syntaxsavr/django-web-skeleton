# Initialise this template

This is a one-time runbook for coding agents. If the user says **"init the
template"**, follow this file before doing other project work. Do not delete it
until initialisation is complete and verified.

## Start with a short interview

Explain that deployment settings, secrets, email credentials, anti-bot keys,
and bootstrap credentials live in `.env`. The file is ignored by Git. Feature
switches and third-party service IDs live in the Django admin unless an
environment override is explicitly supported.

Ask the questions below in one message. Invite short answers and accept sensible
defaults. Do not ask follow-up questions unless an answer is unsafe or prevents
the build.

1. What is the site called, what does it do, who is it for, and what is its
   primary action?
2. Which pages are needed? Ask for available copy, contact details, social links,
   and any must-keep URLs. Never invent testimonials, claims, company details,
   or legal facts.
3. What should it look and feel like? Ask for two or three adjectives, preferred
   and disliked colours, typography preference, light or dark mode, imagery
   direction, and up to three reference sites. Offer to propose the direction
   when the user has no strong preference.
4. How much motion should it use: none, subtle interface motion, or expressive
   animation? Does the user want Lottie? Explain the choices using the motion
   guide below.
5. Where will the organisation and its visitors be based? Will the site use
   analytics, advertising pixels, embeds, payments, newsletters, maps, video,
   or other third-party services? Say that EU or UK visitors commonly require
   prior consent for non-essential storage and tracking. Do not present this as
   legal advice. Ask whether to enable the consent manager. If uncertain, keep
   consent enabled and tracking disabled.
6. Which built-in functions are wanted: contact form, Turnstile, public account
   registration, approval for new accounts, login-only paths, Cal.com, Stripe,
   outbound-link prompts, sitemap, robots.txt, llms.txt, JSON-LD, and IndexNow?
   Keep security headers and spam defences enabled unless there is a concrete
   reason not to.
7. What are the launch domain, default language, time zone, contact recipient,
   hosting platform, and production email provider? It is fine to mark unknown
   production values as TODOs, but development must still run locally.

## Explain motion and Lottie clearly

Use motion to clarify hierarchy and state, not to decorate every surface. Honour
`prefers-reduced-motion`, preserve keyboard behaviour, avoid layout-shifting
properties, and keep important content understandable when JavaScript or motion
is unavailable.

Offer these starting directions:

- **Subtle interface motion:** short fades, small vertical entrances, clear hover
  and focus feedback, gentle modal transitions, and restrained section reveals.
  This suits professional, public-sector, legal, and information-heavy sites.
- **Editorial motion:** masked headline reveals, staggered type or cards, calm
  parallax-like depth, and one memorable hero sequence. It suits studios,
  portfolios, publications, and brands led by typography.
- **Illustrative Lottie:** a small set of looping or scroll-linked vector scenes
  with a shared palette, line weight, shape language, and easing. It suits
  explainers, friendly products, and abstract services. Loops should be quiet,
  optional, and paused when off-screen.
- **Technical Lottie:** diagrams, paths, nodes, counters, or system flows that
  explain a process. Use deliberate timing and state changes. Avoid random
  floating shapes, perpetual background movement, and animation that competes
  with calls to action.

If Lottie is selected, agree on one direction and record its palette, geometry,
line treatment, texture, timing range, easing, loop behaviour, scroll behaviour,
and reduced-motion fallback in `docs/DESIGN-SYSTEM.md`. Reuse those rules across
every animation. Do not mix unrelated animation styles.

## Perform the initialisation

After the user answers:

1. Read `AGENTS.md`, `docs/DESIGN-SYSTEM.md`, and the relevant skills before
   changing files.
2. Turn the design answers into a specific scheme in `docs/DESIGN-SYSTEM.md`:
   concept, colour tokens with contrast intent, type roles, spacing and grid,
   shape and border rules, imagery, component treatment, responsive behaviour,
   interaction states, and the chosen motion language.
3. Copy `.env.example` to `.env` if `.env` does not exist. Preserve any existing
   values. Fill known settings, generate a strong `DJANGO_SECRET_KEY`, replace
   the seed password, and leave unknown secrets blank or clearly marked. Never
   print secret values in chat or commit `.env`.
4. Apply the name, domain, language, time zone, pages, content, brand assets, and
   requested feature switches. Remove demo content that does not fit the site.
5. Configure consent conservatively. Non-essential trackers must remain absent
   until tracking is enabled, an ID exists, and the required consent has been
   given. Add new third-party hosts to CSP and document each service.
6. Treat legal templates as placeholders until the user supplies reviewed legal
   text. Do not claim that generated copy is legally sufficient.
7. Run migrations, `python manage.py test`, and `python manage.py check
   --deploy` with production settings where practical. Report any remaining
   TODOs and the admin URL without exposing credentials.
8. Only after the configured site passes its relevant checks, delete this file:
   `HEY-READ-THIS-FIRST.md`. Do not delete `AGENTS.md` or any skill files.

Finish with a compact handover: what changed, what remains for the owner, where
the switches live, and which legal or deployment details still need review.
