"""Input sanitisation. Every string that arrives from outside (forms,
profile fields, block texts, message bodies) passes through here before
it is stored. The default strips ALL markup: the skeleton renders text,
it never re-displays HTML.

If a future feature genuinely needs rich text, add a dedicated allow-list
function here (bleach.clean with explicit tags) - never bypass this module.
"""

import bleach


def clean_text(value: str) -> str:
    """Strip every tag and attribute; collapse surrounding whitespace."""
    if not value:
        return ""
    return bleach.clean(str(value), tags=[], attributes={}, strip=True).strip()


def clean_multiline(value: str) -> str:
    """clean_text, but keeps inner line breaks."""
    if not value:
        return ""
    cleaned = bleach.clean(str(value), tags=[], attributes={}, strip=True)
    lines = [line.strip() for line in cleaned.splitlines()]
    return "\n".join(lines).strip()
