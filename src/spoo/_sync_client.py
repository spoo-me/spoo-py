from __future__ import annotations

from datetime import datetime
from functools import cached_property
from typing import Any

import httpx

from ._base_client import _BaseClient
from ._resources.links import Links
from ._resources.oauth import OAuth
from ._resources.stats import Stats
from ._transport import SyncTransport
from .types.link import CreatedLink
from .types.oauth import MeEnvelope, UserProfile


class SpooClient(_BaseClient):
    """Sync client for the spoo.me API.

    Usage::

        client = SpooClient(api_key="spoo_...")
        url = client.shorten("https://example.com")
    """

    def __init__(self, *, http_client: httpx.Client | None = None, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._transport = SyncTransport(
            base_url=self._base_url,
            auth=self._auth,
            timeout=self._timeout,
            max_retries=self._max_retries,
            custom_headers=self._custom_headers,
            http_client=http_client,
        )

    def request(
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
        return self._transport.request_json(method, path, params=params, json=json)

    @cached_property
    def links(self) -> Links:
        return Links(self._transport)

    @cached_property
    def stats(self) -> Stats:
        return Stats(self._transport)

    @cached_property
    def oauth(self) -> OAuth:
        return OAuth(self._transport, self._site_root)

    def me(self) -> UserProfile:
        """The authenticated user's profile, read-only (GET /auth/me)."""
        envelope = self._transport.request("GET", f"{self._site_root}/auth/me", cast_to=MeEnvelope)
        return envelope.user

    def shorten(
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
    ) -> CreatedLink:
        """Convenience: shorten a URL in one call."""
        return self.links.create(
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

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> SpooClient:
        return self

    def __exit__(self, *args) -> None:  # type: ignore[no-untyped-def]
        self.close()
