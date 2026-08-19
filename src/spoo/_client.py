from __future__ import annotations

from datetime import datetime
from functools import cached_property
from typing import Any

import httpx

from ._base_client import _BaseClient
from ._resources.oauth import AsyncOAuth
from ._resources.stats import AsyncStats
from ._resources.urls import AsyncURLs
from ._transport import AsyncTransport
from .types.oauth import MeEnvelope, UserProfile
from .types.url import ShortenedUrl


class AsyncSpooClient(_BaseClient):
    """Async client for the spoo.me API.

    Usage::

        async with AsyncSpooClient(api_key="spoo_...") as client:
            url = await client.shorten("https://example.com")
    """

    def __init__(self, *, http_client: httpx.AsyncClient | None = None, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._transport = AsyncTransport(
            base_url=self._base_url,
            auth=self._auth,
            timeout=self._timeout,
            max_retries=self._max_retries,
            custom_headers=self._custom_headers,
            http_client=http_client,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Escape hatch: call any API path with the client's auth, retries,
        and error mapping applied. Returns the parsed JSON body.

        ``path`` is relative to the base URL (``"/urls"``) or absolute. If
        you reach for this, the SDK has a coverage gap worth filing.
        """
        return await self._transport.request_json(method, path, params=params, json=json)

    @cached_property
    def urls(self) -> AsyncURLs:
        return AsyncURLs(self._transport)

    @cached_property
    def stats(self) -> AsyncStats:
        return AsyncStats(self._transport)

    @cached_property
    def oauth(self) -> AsyncOAuth:
        return AsyncOAuth(self._transport, self._site_root)

    async def me(self) -> UserProfile:
        """The authenticated user's profile, read-only (GET /auth/me)."""
        envelope = await self._transport.request(
            "GET", f"{self._site_root}/auth/me", cast_to=MeEnvelope
        )
        return envelope.user

    async def shorten(
        self,
        long_url: str,
        *,
        alias: str | None = None,
        alias_type: str | None = None,
        password: str | None = None,
        block_bots: bool | None = None,
        max_clicks: int | None = None,
        expire_after: str | int | datetime | None = None,
        private_stats: bool | None = None,
        domain: str | None = None,
    ) -> ShortenedUrl:
        """Convenience: shorten a URL in one call."""
        return await self.urls.create(
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

    async def close(self) -> None:
        await self._transport.close()

    async def __aenter__(self) -> AsyncSpooClient:
        return self

    async def __aexit__(self, *args) -> None:  # type: ignore[no-untyped-def]
        await self.close()
