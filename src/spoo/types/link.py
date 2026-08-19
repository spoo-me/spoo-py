from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from .shared import LinkStatus, enum_value


class CreatedLink(BaseModel):
    """Response from POST /api/v1/shorten."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    # Stable identifier: what stats.for_link() / stats.export_link()
    # and the /urls/{url_id} endpoints address the link by.
    id: str | None = None
    alias: str
    short_url: str
    long_url: str
    owner_id: str | None = None
    created_at: int
    status: str
    private_stats: bool | None = None
    claim_token: str | None = None
    """One-time bearer token returned on anonymous creates.

    Present only when the URL was created without authentication. Hold on to
    it: an authenticated client can later take ownership of the link with
    ``client.links.claim(url.id, url.claim_token)``. It is never shown again.
    """


class Link(BaseModel):
    """A single URL in a list response."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    alias: str | None = None
    long_url: str | None = None
    status: str | None = None
    created_at: str | None = None
    expire_after: int | None = None
    max_clicks: int | None = None
    private_stats: bool | None = None
    block_bots: bool | None = None
    password_set: bool
    total_clicks: int | None = None
    last_click: str | None = None
    domain: str | None = None


class LinkPage(BaseModel):
    """Response from GET /api/v1/urls."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    items: list[Link]
    page: int
    pageSize: int
    total: int
    hasNext: bool
    sortBy: str
    sortOrder: str


class UpdatedLink(BaseModel):
    """Response from PATCH /api/v1/urls/{id}."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    alias: str | None = None
    long_url: str | None = None
    status: str | None = None
    password_set: bool
    max_clicks: int | None = None
    expire_after: int | None = None
    block_bots: bool | None = None
    private_stats: bool | None = None
    domain: str | None = None
    updated_at: int


class DeletedLink(BaseModel):
    """Response from DELETE /api/v1/urls/{id}."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    message: str
    id: str


class BulkDeletedLinks(BaseModel):
    """Response from DELETE /api/v1/urls?domain=<fqdn> (bulk delete)."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    message: str
    count: int
    domain: str


class AliasCheck(BaseModel):
    """Response from GET /api/v1/shorten/check-alias.

    ``available`` is true only when the alias passes format/length validation
    and is not already taken. When false, ``reason`` is one of ``"length"``,
    ``"format"``, ``"reserved"``, ``"taken"``, or ``"emoji_policy"``.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    available: bool
    reason: str | None = None


class ClaimResult(BaseModel):
    """One outcome in a claim batch (POST /api/v1/urls/claim).

    ``status`` is ``"claimed"`` (ownership transferred, token burned),
    ``"already_yours"`` (idempotent repeat), or ``"invalid"`` (unknown id,
    wrong token, or an unclaimable link; deliberately indistinguishable).
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    url_id: str
    status: str


class ClaimedLinks(BaseModel):
    """Response from POST /api/v1/urls/claim. Never hard-fails per item."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    results: list[ClaimResult]
    claimed: int


class BulkSummary(BaseModel):
    """Counts for one bulk operation."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    total: int
    succeeded: int
    failed: int


class BulkResultRow(BaseModel):
    """Per-URL outcome of a bulk operation."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    alias: str | None = None
    ok: bool
    error_code: str | None = None
    error: str | None = None


class PreviewDestination(BaseModel):
    """Where a link points, as shown on the public preview."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    url: str
    domain: str
    path: str
    is_https: bool


class PublicPreview(BaseModel):
    """Response from GET /api/v1/public/preview/{short_code}.

    The unauthenticated "what is this link" read: what a bot, integration,
    or safety check calls before following a short link. ``destination`` is
    None for inactive/blocked links; geo-targeted links list per-country
    destinations instead.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    generation: str
    alias: str
    short_url: str
    status: str
    created_at: str | None = None
    password_protected: bool
    destination: PreviewDestination | None = None
    geo_destinations: list[dict[str, Any]] | None = None


class BulkResult(BaseModel):
    """Response from POST /api/v1/urls/bulk/{delete,status,expiry,domain}."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    summary: BulkSummary
    results: list[BulkResultRow]


class LinkFilter:
    """Filter object for list URLs query. Serialized to JSON query param."""

    def __init__(
        self,
        *,
        status: str | LinkStatus | None = None,
        created_after: str | int | None = None,
        created_before: str | int | None = None,
        password_set: bool | None = None,
        max_clicks_set: bool | None = None,
        search: str | None = None,
    ) -> None:
        self.status = enum_value(status) if status else None
        self.created_after = created_after
        self.created_before = created_before
        self.password_set = password_set
        self.max_clicks_set = max_clicks_set
        self.search = search

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.status is not None:
            d["status"] = self.status
        if self.created_after is not None:
            d["createdAfter"] = self.created_after
        if self.created_before is not None:
            d["createdBefore"] = self.created_before
        if self.password_set is not None:
            d["passwordSet"] = self.password_set
        if self.max_clicks_set is not None:
            d["maxClicksSet"] = self.max_clicks_set
        if self.search is not None:
            d["search"] = self.search
        return d
