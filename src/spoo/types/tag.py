from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

# Literal, not the shared Enum: autocomplete over a closed set; `| str` at call sites keeps it open.
TagColor = Literal[
    "gray",
    "red",
    "orange",
    "amber",
    "green",
    "teal",
    "blue",
    "violet",
    "pink",
]

TagIcon = Literal[
    "banknote",
    "bar-chart-3",
    "beaker",
    "bell",
    "bird",
    "book",
    "bookmark",
    "box",
    "briefcase",
    "bug",
    "building",
    "calendar",
    "camera",
    "car",
    "cat",
    "clock",
    "cloud",
    "code",
    "coffee",
    "compass",
    "credit-card",
    "crown",
    "dog",
    "file-text",
    "fish",
    "flag",
    "flame",
    "flask-conical",
    "folder",
    "gamepad-2",
    "gem",
    "ghost",
    "gift",
    "globe",
    "graduation-cap",
    "handshake",
    "hash",
    "heart",
    "home",
    "hourglass",
    "image",
    "key",
    "layers",
    "leaf",
    "lightbulb",
    "link",
    "lock",
    "mail",
    "map-pin",
    "megaphone",
    "message-square",
    "mic",
    "moon",
    "music",
    "newspaper",
    "package",
    "pen-line",
    "phone",
    "pie-chart",
    "pizza",
    "plane",
    "puzzle",
    "receipt",
    "rocket",
    "send",
    "settings",
    "share-2",
    "shield",
    "shopping-cart",
    "smile",
    "sparkles",
    "star",
    "store",
    "sun",
    "tag",
    "target",
    "terminal",
    "timer",
    "trending-up",
    "trophy",
    "umbrella",
    "user",
    "users",
    "video",
    "wallet",
    "wrench",
    "zap",
]

TagsMatch = Literal["any", "all"]


class TagRef(BaseModel):
    """A tag as it appears on a link: enough to render, no counts.

    ``color`` and ``icon`` are typed as ``str`` so a palette or icon the
    server adds later still parses; the accepted keys are :data:`TagColor`
    and :data:`TagIcon`.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    name: str
    color: str
    icon: str


class Tag(TagRef):
    """A tag from the /tags endpoints, with its link count."""

    link_count: int
    created_at: str
    updated_at: str | None = None


class TagList(BaseModel):
    """Response from GET /api/v1/tags."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    items: list[Tag]


class DeletedTag(BaseModel):
    """Response from DELETE /api/v1/tags/{tag_id}."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    deleted: bool = True
    links_updated: int
