"""Client-side validation — instant feedback before HTTP round-trip."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_ALIAS_RE = re.compile(r"^[a-zA-Z0-9_-]{3,16}$")
_HAS_LETTER = re.compile(r"[a-zA-Z]")
_HAS_DIGIT = re.compile(r"\d")
_HAS_SPECIAL = re.compile(r"[@.]")


def validate_url(url: str) -> None:
    """Validate that a URL is http:// or https://."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must start with http:// or https://, got: {url!r}")
    if not parsed.netloc:
        raise ValueError(f"URL is missing a hostname: {url!r}")


def validate_alias(alias: str) -> None:
    """Validate custom alias format: 3-16 chars, alphanumeric/hyphens/underscores."""
    if not _ALIAS_RE.match(alias):
        raise ValueError(
            f"Alias must be 3-16 characters, alphanumeric, hyphens, or underscores. Got: {alias!r}"
        )


def validate_password(password: str) -> None:
    """Validate password: 8+ chars, must contain letter + digit + special char (@ or .)."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not _HAS_LETTER.search(password):
        raise ValueError("Password must contain at least one letter")
    if not _HAS_DIGIT.search(password):
        raise ValueError("Password must contain at least one digit")
    if not _HAS_SPECIAL.search(password):
        raise ValueError("Password must contain at least one special character (@ or .)")


def validate_max_clicks(max_clicks: int) -> None:
    """Validate max_clicks is a positive integer."""
    if max_clicks <= 0:
        raise ValueError(f"max_clicks must be a positive integer, got: {max_clicks}")


# ── Emoji aliases ─────────────────────────────────────────────────────────

_VS16 = "️"
_SKIN_TONES = frozenset(chr(cp) for cp in range(0x1F3FB, 0x1F400))


def is_emoji_candidate(alias: str) -> bool:
    """Whether an alias should take the emoji validation path (any non-ASCII)."""
    return any(ord(ch) > 127 for ch in alias)


def canonicalize_emoji(value: str) -> str:
    """Strip variation selectors and skin-tone modifiers, mirroring the server
    policy where the base emoji stands for all presentation variants."""
    return "".join(ch for ch in value if ch != _VS16 and ch not in _SKIN_TONES)


def validate_emoji_alias(alias: str, accepted: frozenset[str], max_graphemes: int) -> None:
    """Validate an emoji alias against the server's accepted emoji catalogue.

    Greedy longest-match tokenization over the accepted set (entries can be
    multi-codepoint). Raises ValueError naming the first unaccepted segment.
    """
    canonical = canonicalize_emoji(alias)
    if not canonical:
        raise ValueError(f"Alias contains no emoji: {alias!r}")

    max_token_len = max(len(e) for e in accepted)
    count = 0
    i = 0
    while i < len(canonical):
        for length in range(min(max_token_len, len(canonical) - i), 0, -1):
            if canonical[i : i + length] in accepted:
                i += length
                count += 1
                break
        else:
            raise ValueError(
                f"{canonical[i]!r} is not in the accepted emoji set (see client.urls.emoji_set())"
            )
    if count > max_graphemes:
        raise ValueError(f"Emoji alias is limited to {max_graphemes} emoji, got {count}")
