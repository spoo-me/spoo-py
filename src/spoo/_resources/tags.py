from __future__ import annotations

from typing import Any

from ..types.tag import DeletedTag, Tag, TagColor, TagIcon, TagList
from ._base import AsyncAPIResource, SyncAPIResource

# ── Shared pure functions (used by both sync and async) ──────────────────


def _build_tag_body(
    *,
    name: str | None,
    color: TagColor | str | None,
    icon: TagIcon | str | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if color is not None:
        body["color"] = color
    if icon is not None:
        body["icon"] = icon
    return body


# ── Async resource ───────────────────────────────────────────────────────


class AsyncTags(AsyncAPIResource):
    """Link tags: a per-account label set links carry by id (async)."""

    async def list(self) -> list[Tag]:
        """Every tag in your account with its link count, oldest first."""
        envelope = await self._transport.request("GET", "/tags", cast_to=TagList)
        return envelope.items

    async def create(
        self,
        name: str,
        *,
        color: TagColor | str | None = None,
        icon: TagIcon | str | None = None,
    ) -> Tag:
        """Create a tag. Names are lowercased and trimmed; a duplicate answers 409.

        Omit ``color`` for the least-used palette colour in your account and
        ``icon`` for the generic tag glyph.
        """
        body = _build_tag_body(name=name, color=color, icon=icon)
        return await self._transport.request("POST", "/tags", json=body, cast_to=Tag)

    async def update(
        self,
        tag_id: str,
        *,
        name: str | None = None,
        color: TagColor | str | None = None,
        icon: TagIcon | str | None = None,
    ) -> Tag:
        """Rename, recolour or change the icon. Omitted fields are left as they are."""
        body = _build_tag_body(name=name, color=color, icon=icon)
        return await self._transport.request("PATCH", f"/tags/{tag_id}", json=body, cast_to=Tag)

    async def delete(self, tag_id: str) -> DeletedTag:
        """Delete the tag and strip it from every link that carried it."""
        return await self._transport.request("DELETE", f"/tags/{tag_id}", cast_to=DeletedTag)


# ── Sync resource ────────────────────────────────────────────────────────


class Tags(SyncAPIResource):
    """Link tags: a per-account label set links carry by id (sync)."""

    def list(self) -> list[Tag]:
        """Every tag in your account with its link count, oldest first."""
        envelope = self._transport.request("GET", "/tags", cast_to=TagList)
        return envelope.items

    def create(
        self,
        name: str,
        *,
        color: TagColor | str | None = None,
        icon: TagIcon | str | None = None,
    ) -> Tag:
        """Create a tag. Names are lowercased and trimmed; a duplicate answers 409.

        Omit ``color`` for the least-used palette colour in your account and
        ``icon`` for the generic tag glyph.
        """
        body = _build_tag_body(name=name, color=color, icon=icon)
        return self._transport.request("POST", "/tags", json=body, cast_to=Tag)

    def update(
        self,
        tag_id: str,
        *,
        name: str | None = None,
        color: TagColor | str | None = None,
        icon: TagIcon | str | None = None,
    ) -> Tag:
        """Rename, recolour or change the icon. Omitted fields are left as they are."""
        body = _build_tag_body(name=name, color=color, icon=icon)
        return self._transport.request("PATCH", f"/tags/{tag_id}", json=body, cast_to=Tag)

    def delete(self, tag_id: str) -> DeletedTag:
        """Delete the tag and strip it from every link that carried it."""
        return self._transport.request("DELETE", f"/tags/{tag_id}", cast_to=DeletedTag)
