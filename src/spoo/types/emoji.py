from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EmojiEntry(BaseModel):
    """One emoji in the accepted alias catalogue (wire-compact field names)."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    c: str
    """The emoji character itself."""
    n: str
    """Display name."""
    g: str
    """Unicode group (e.g. "Smileys & Emotion")."""
    gen: bool
    """Whether this emoji is in the auto-generation pool."""
    k: list[str] | None = None
    """Search keywords, when distinct from the name."""


class EmojiSet(BaseModel):
    """Response from GET /api/v1/emoji-set: the emoji-alias acceptance policy.

    ``emoji`` lists every accepted emoji; skin-tone variants are not
    enumerated (the base emoji stands for all tones). ``max_graphemes`` is
    the alias length cap in emoji count.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    accept_max_version: float
    generate_max_version: float
    max_graphemes: int
    emoji: list[EmojiEntry]
