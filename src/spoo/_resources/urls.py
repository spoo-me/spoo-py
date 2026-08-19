from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlparse

from .._pagination import AsyncPaginator, SyncPaginator
from .._validators import (
    canonicalize_emoji,
    is_emoji_candidate,
    validate_alias,
    validate_emoji_alias,
    validate_max_clicks,
    validate_password,
    validate_url,
)
from ..types.emoji import EmojiSet
from ..types.shared import AliasType, SortBy, SortOrder, UrlStatus, enum_value
from ..types.url import (
    AliasCheck,
    BulkDeletedUrls,
    BulkResult,
    ClaimedUrls,
    ClaimResult,
    DeletedUrl,
    ShortenedUrl,
    UpdatedUrl,
    UrlFilter,
    UrlListItem,
    UrlListResponse,
)
from ._base import AsyncAPIResource, SyncAPIResource

# ── Shared pure functions (used by both sync and async) ──────────────────


def _build_create_body(
    long_url: str,
    *,
    alias: str | None,
    alias_type: AliasType | str | None,
    password: str | None,
    block_bots: bool | None,
    max_clicks: int | None,
    expire_after: str | int | datetime | None,
    private_stats: bool | None,
    domain: str | None,
) -> dict[str, Any]:
    validate_url(long_url)
    if password is not None:
        validate_password(password)
    if max_clicks is not None:
        validate_max_clicks(max_clicks)

    body: dict[str, Any] = {"long_url": long_url}
    if alias is not None:
        body["alias"] = alias
    if alias_type is not None:
        body["alias_type"] = enum_value(alias_type)
    if password is not None:
        body["password"] = password
    if block_bots is not None:
        body["block_bots"] = block_bots
    if max_clicks is not None:
        body["max_clicks"] = max_clicks
    if expire_after is not None:
        body["expire_after"] = _serialize_datetime(expire_after)
    if private_stats is not None:
        body["private_stats"] = private_stats
    if domain is not None:
        body["domain"] = domain
    return body


def _build_claim_body(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    return {"claims": [{"url_id": url_id, "token": token} for url_id, token in pairs]}


def _emoji_vocabulary(emoji_set: EmojiSet) -> frozenset[str]:
    return frozenset(canonicalize_emoji(entry.c) for entry in emoji_set.emoji) - {""}


def _build_update_body(
    *,
    long_url: str | None,
    alias: str | None,
    password: str | None,
    block_bots: bool | None,
    max_clicks: int | None,
    expire_after: str | int | datetime | None,
    private_stats: bool | None,
    status: UrlStatus | str | None,
    domain: str | None,
) -> dict[str, Any]:
    if long_url is not None:
        validate_url(long_url)
    if password is not None:
        validate_password(password)
    if max_clicks is not None and max_clicks > 0:
        validate_max_clicks(max_clicks)

    body: dict[str, Any] = {}
    if long_url is not None:
        body["long_url"] = long_url
    if alias is not None:
        body["alias"] = alias
    if password is not None:
        body["password"] = password
    if block_bots is not None:
        body["block_bots"] = block_bots
    if max_clicks is not None:
        body["max_clicks"] = max_clicks
    if expire_after is not None:
        body["expire_after"] = _serialize_datetime(expire_after)
    if private_stats is not None:
        body["private_stats"] = private_stats
    if status is not None:
        body["status"] = enum_value(status)
    if domain is not None:
        body["domain"] = domain
    return body


def _build_list_params(
    *,
    page: int,
    page_size: int,
    sort_by: SortBy | str,
    sort_order: SortOrder | str,
    filter: UrlFilter | dict[str, Any] | None,
    domain: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "page": page,
        "pageSize": page_size,
        "sortBy": enum_value(sort_by),
        "sortOrder": enum_value(sort_order),
    }
    if filter is not None:
        filter_dict = filter.to_dict() if isinstance(filter, UrlFilter) else filter
        if filter_dict:
            params["filter"] = json.dumps(filter_dict)
    if domain is not None:
        params["domain"] = domain
    return params


def _serialize_datetime(value: str | int | datetime) -> str | int:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


# ── Async resource ───────────────────────────────────────────────────────


class AsyncURLs(AsyncAPIResource):
    """URL shortening and management (async)."""

    _emoji_set_cache: EmojiSet | None = None

    async def create(
        self,
        long_url: str,
        *,
        alias: str | None = None,
        alias_type: AliasType | str | None = None,
        password: str | None = None,
        block_bots: bool | None = None,
        max_clicks: int | None = None,
        expire_after: str | int | datetime | None = None,
        private_stats: bool | None = None,
        domain: str | None = None,
    ) -> ShortenedUrl:
        if alias is not None:
            if is_emoji_candidate(alias):
                await self._validate_emoji_alias(alias)
            else:
                validate_alias(alias)
        body = _build_create_body(
            long_url,
            alias=alias,
            alias_type=alias_type,
            password=password,
            block_bots=block_bots,
            max_clicks=max_clicks,
            expire_after=expire_after,
            private_stats=private_stats,
            domain=domain,
        )
        return await self._transport.request("POST", "/shorten", json=body, cast_to=ShortenedUrl)

    async def get(self, url_id: str) -> UrlListItem:
        """Fetch one URL you own by its id."""
        return await self._transport.request("GET", f"/urls/{url_id}", cast_to=UrlListItem)

    async def get_by_alias(self, alias: str, *, domain: str | None = None) -> UrlListItem:
        """Fetch one URL you own by its natural key: alias plus serving domain.

        ``domain`` defaults to the host of the client's base URL (the system
        domain); pass a custom domain fqdn for links scoped under one.
        """
        resolved = domain or urlparse(str(self._transport._base_url)).hostname or "spoo.me"
        return await self._transport.request(
            "GET", f"/urls/{resolved}/{quote(alias)}", cast_to=UrlListItem
        )

    async def claim(self, url_id: str, token: str) -> ClaimResult:
        """Claim one anonymously created URL into the authenticated account.

        ``token`` is the ``claim_token`` from the anonymous shorten response.
        """
        result = await self.claim_many([(url_id, token)])
        return result.results[0]

    async def claim_many(self, pairs: list[tuple[str, str]]) -> ClaimedUrls:
        """Claim up to 16 anonymously created URLs, as (url_id, claim_token) pairs."""
        return await self._transport.request(
            "POST", "/urls/claim", json=_build_claim_body(pairs), cast_to=ClaimedUrls
        )

    async def emoji_set(self, *, refresh: bool = False) -> EmojiSet:
        """The emoji-alias acceptance policy, cached for the client's lifetime."""
        if self._emoji_set_cache is None or refresh:
            self._emoji_set_cache = await self._transport.request(
                "GET", "/emoji-set", cast_to=EmojiSet
            )
        return self._emoji_set_cache

    async def _validate_emoji_alias(self, alias: str) -> None:
        # Best-effort: the server is the authority, so a failed catalogue
        # fetch skips client-side validation rather than blocking the create.
        try:
            emoji_set = await self.emoji_set()
        except Exception:  # noqa: BLE001
            return
        validate_emoji_alias(alias, _emoji_vocabulary(emoji_set), emoji_set.max_graphemes)

    async def bulk_delete(self, ids: list[str]) -> BulkResult:
        """Delete up to 100 URLs by id. Per-item outcomes, never hard-fails."""
        return await self._transport.request(
            "POST", "/urls/bulk/delete", json={"ids": ids}, cast_to=BulkResult
        )

    async def bulk_set_status(self, ids: list[str], status: UrlStatus | str) -> BulkResult:
        """Set ACTIVE/INACTIVE on up to 100 URLs by id."""
        return await self._transport.request(
            "POST",
            "/urls/bulk/status",
            json={"ids": ids, "status": enum_value(status)},
            cast_to=BulkResult,
        )

    async def bulk_set_expiry(
        self, ids: list[str], expire_after: str | int | datetime | None
    ) -> BulkResult:
        """Set or clear (None) the expiry on up to 100 URLs by id."""
        expiry = _serialize_datetime(expire_after) if expire_after is not None else None
        return await self._transport.request(
            "POST",
            "/urls/bulk/expiry",
            json={"ids": ids, "expire_after": expiry},
            cast_to=BulkResult,
        )

    async def bulk_set_domain(self, ids: list[str], domain: str | None) -> BulkResult:
        """Move up to 100 URLs to a custom domain, or back to the default (None)."""
        return await self._transport.request(
            "POST",
            "/urls/bulk/domain",
            json={"ids": ids, "domain": domain},
            cast_to=BulkResult,
        )

    async def check_alias(self, alias: str, *, domain: str | None = None) -> AliasCheck:
        params: dict[str, Any] = {"alias": alias}
        if domain is not None:
            params["domain"] = domain
        return await self._transport.request(
            "GET", "/shorten/check-alias", params=params, cast_to=AliasCheck
        )

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        sort_by: SortBy | str = SortBy.CREATED_AT,
        sort_order: SortOrder | str = SortOrder.DESCENDING,
        filter: UrlFilter | dict[str, Any] | None = None,
        domain: str | None = None,
    ) -> AsyncPaginator:
        params = {
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "filter": filter,
            "domain": domain,
        }
        return AsyncPaginator(fetch_page=self.list_page, params=params)

    async def list_page(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        sort_by: SortBy | str = SortBy.CREATED_AT,
        sort_order: SortOrder | str = SortOrder.DESCENDING,
        filter: UrlFilter | dict[str, Any] | None = None,
        domain: str | None = None,
    ) -> UrlListResponse:
        params = _build_list_params(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
            domain=domain,
        )
        return await self._transport.request("GET", "/urls", params=params, cast_to=UrlListResponse)

    async def update(
        self,
        url_id: str,
        *,
        long_url: str | None = None,
        alias: str | None = None,
        password: str | None = None,
        block_bots: bool | None = None,
        max_clicks: int | None = None,
        expire_after: str | int | datetime | None = None,
        private_stats: bool | None = None,
        status: UrlStatus | str | None = None,
        domain: str | None = None,
    ) -> UpdatedUrl:
        if alias is not None:
            if is_emoji_candidate(alias):
                await self._validate_emoji_alias(alias)
            else:
                validate_alias(alias)
        body = _build_update_body(
            long_url=long_url,
            alias=alias,
            password=password,
            block_bots=block_bots,
            max_clicks=max_clicks,
            expire_after=expire_after,
            private_stats=private_stats,
            status=status,
            domain=domain,
        )
        return await self._transport.request(
            "PATCH", f"/urls/{url_id}", json=body, cast_to=UpdatedUrl
        )

    async def set_status(self, url_id: str, status: UrlStatus | str) -> UpdatedUrl:
        return await self._transport.request(
            "PATCH",
            f"/urls/{url_id}/status",
            json={"status": enum_value(status)},
            cast_to=UpdatedUrl,
        )

    async def delete(self, url_id: str) -> DeletedUrl:
        return await self._transport.request("DELETE", f"/urls/{url_id}", cast_to=DeletedUrl)

    async def delete_all(self, domain: str) -> BulkDeletedUrls:
        """Delete every URL scoped under a custom domain."""
        return await self._transport.request(
            "DELETE", "/urls", params={"domain": domain}, cast_to=BulkDeletedUrls
        )


# ── Sync resource ────────────────────────────────────────────────────────


class URLs(SyncAPIResource):
    """URL shortening and management (sync)."""

    _emoji_set_cache: EmojiSet | None = None

    def create(
        self,
        long_url: str,
        *,
        alias: str | None = None,
        alias_type: AliasType | str | None = None,
        password: str | None = None,
        block_bots: bool | None = None,
        max_clicks: int | None = None,
        expire_after: str | int | datetime | None = None,
        private_stats: bool | None = None,
        domain: str | None = None,
    ) -> ShortenedUrl:
        if alias is not None:
            if is_emoji_candidate(alias):
                self._validate_emoji_alias(alias)
            else:
                validate_alias(alias)
        body = _build_create_body(
            long_url,
            alias=alias,
            alias_type=alias_type,
            password=password,
            block_bots=block_bots,
            max_clicks=max_clicks,
            expire_after=expire_after,
            private_stats=private_stats,
            domain=domain,
        )
        return self._transport.request("POST", "/shorten", json=body, cast_to=ShortenedUrl)

    def get(self, url_id: str) -> UrlListItem:
        """Fetch one URL you own by its id."""
        return self._transport.request("GET", f"/urls/{url_id}", cast_to=UrlListItem)

    def get_by_alias(self, alias: str, *, domain: str | None = None) -> UrlListItem:
        """Fetch one URL you own by its natural key: alias plus serving domain.

        ``domain`` defaults to the host of the client's base URL (the system
        domain); pass a custom domain fqdn for links scoped under one.
        """
        resolved = domain or urlparse(str(self._transport._base_url)).hostname or "spoo.me"
        return self._transport.request(
            "GET", f"/urls/{resolved}/{quote(alias)}", cast_to=UrlListItem
        )

    def claim(self, url_id: str, token: str) -> ClaimResult:
        """Claim one anonymously created URL into the authenticated account.

        ``token`` is the ``claim_token`` from the anonymous shorten response.
        """
        result = self.claim_many([(url_id, token)])
        return result.results[0]

    def claim_many(self, pairs: list[tuple[str, str]]) -> ClaimedUrls:
        """Claim up to 16 anonymously created URLs, as (url_id, claim_token) pairs."""
        return self._transport.request(
            "POST", "/urls/claim", json=_build_claim_body(pairs), cast_to=ClaimedUrls
        )

    def emoji_set(self, *, refresh: bool = False) -> EmojiSet:
        """The emoji-alias acceptance policy, cached for the client's lifetime."""
        if self._emoji_set_cache is None or refresh:
            self._emoji_set_cache = self._transport.request("GET", "/emoji-set", cast_to=EmojiSet)
        return self._emoji_set_cache

    def _validate_emoji_alias(self, alias: str) -> None:
        # Best-effort: the server is the authority, so a failed catalogue
        # fetch skips client-side validation rather than blocking the create.
        try:
            emoji_set = self.emoji_set()
        except Exception:  # noqa: BLE001
            return
        validate_emoji_alias(alias, _emoji_vocabulary(emoji_set), emoji_set.max_graphemes)

    def bulk_delete(self, ids: list[str]) -> BulkResult:
        """Delete up to 100 URLs by id. Per-item outcomes, never hard-fails."""
        return self._transport.request(
            "POST", "/urls/bulk/delete", json={"ids": ids}, cast_to=BulkResult
        )

    def bulk_set_status(self, ids: list[str], status: UrlStatus | str) -> BulkResult:
        """Set ACTIVE/INACTIVE on up to 100 URLs by id."""
        return self._transport.request(
            "POST",
            "/urls/bulk/status",
            json={"ids": ids, "status": enum_value(status)},
            cast_to=BulkResult,
        )

    def bulk_set_expiry(
        self, ids: list[str], expire_after: str | int | datetime | None
    ) -> BulkResult:
        """Set or clear (None) the expiry on up to 100 URLs by id."""
        expiry = _serialize_datetime(expire_after) if expire_after is not None else None
        return self._transport.request(
            "POST",
            "/urls/bulk/expiry",
            json={"ids": ids, "expire_after": expiry},
            cast_to=BulkResult,
        )

    def bulk_set_domain(self, ids: list[str], domain: str | None) -> BulkResult:
        """Move up to 100 URLs to a custom domain, or back to the default (None)."""
        return self._transport.request(
            "POST",
            "/urls/bulk/domain",
            json={"ids": ids, "domain": domain},
            cast_to=BulkResult,
        )

    def check_alias(self, alias: str, *, domain: str | None = None) -> AliasCheck:
        params: dict[str, Any] = {"alias": alias}
        if domain is not None:
            params["domain"] = domain
        return self._transport.request(
            "GET", "/shorten/check-alias", params=params, cast_to=AliasCheck
        )

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        sort_by: SortBy | str = SortBy.CREATED_AT,
        sort_order: SortOrder | str = SortOrder.DESCENDING,
        filter: UrlFilter | dict[str, Any] | None = None,
        domain: str | None = None,
    ) -> SyncPaginator:
        params = {
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "filter": filter,
            "domain": domain,
        }
        return SyncPaginator(fetch_page=self.list_page, params=params)

    def list_page(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        sort_by: SortBy | str = SortBy.CREATED_AT,
        sort_order: SortOrder | str = SortOrder.DESCENDING,
        filter: UrlFilter | dict[str, Any] | None = None,
        domain: str | None = None,
    ) -> UrlListResponse:
        params = _build_list_params(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
            domain=domain,
        )
        return self._transport.request("GET", "/urls", params=params, cast_to=UrlListResponse)

    def update(
        self,
        url_id: str,
        *,
        long_url: str | None = None,
        alias: str | None = None,
        password: str | None = None,
        block_bots: bool | None = None,
        max_clicks: int | None = None,
        expire_after: str | int | datetime | None = None,
        private_stats: bool | None = None,
        status: UrlStatus | str | None = None,
        domain: str | None = None,
    ) -> UpdatedUrl:
        if alias is not None:
            if is_emoji_candidate(alias):
                self._validate_emoji_alias(alias)
            else:
                validate_alias(alias)
        body = _build_update_body(
            long_url=long_url,
            alias=alias,
            password=password,
            block_bots=block_bots,
            max_clicks=max_clicks,
            expire_after=expire_after,
            private_stats=private_stats,
            status=status,
            domain=domain,
        )
        return self._transport.request("PATCH", f"/urls/{url_id}", json=body, cast_to=UpdatedUrl)

    def set_status(self, url_id: str, status: UrlStatus | str) -> UpdatedUrl:
        return self._transport.request(
            "PATCH",
            f"/urls/{url_id}/status",
            json={"status": enum_value(status)},
            cast_to=UpdatedUrl,
        )

    def delete(self, url_id: str) -> DeletedUrl:
        return self._transport.request("DELETE", f"/urls/{url_id}", cast_to=DeletedUrl)

    def delete_all(self, domain: str) -> BulkDeletedUrls:
        """Delete every URL scoped under a custom domain."""
        return self._transport.request(
            "DELETE", "/urls", params={"domain": domain}, cast_to=BulkDeletedUrls
        )
