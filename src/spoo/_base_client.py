from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlparse

import httpx

from ._auth import ApiKeyAuth, AuthStrategy, BearerTokenAuth, DynamicBearerAuth, NoAuth
from ._constants import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    ENV_API_KEY,
    ENV_BASE_URL,
)


class _BaseClient:
    """Shared configuration for sync and async clients. Performs no I/O."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        bearer_token: str | Callable[[], Any] | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | httpx.Timeout | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        # Auth resolution: explicit > env > anonymous. ``bearer_token`` takes
        # a static JWT or a callable returning the current one (see
        # ``client.oauth.token_provider``). An explicit empty string opts out
        # of env auth entirely: ``SpooClient(api_key="")`` is always anonymous.
        if api_key:
            self._auth: AuthStrategy = ApiKeyAuth(api_key)
        elif callable(bearer_token):
            self._auth = DynamicBearerAuth(bearer_token)
        elif bearer_token:
            self._auth = BearerTokenAuth(bearer_token)
        elif api_key is None and bearer_token is None:
            env_key = os.environ.get(ENV_API_KEY)
            self._auth = ApiKeyAuth(env_key) if env_key else NoAuth()
        else:
            self._auth = NoAuth()

        # Base URL
        if base_url is not None:
            self._base_url = str(base_url)
        else:
            self._base_url = os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL)

        # Timeout
        if timeout is None:
            self._timeout = DEFAULT_TIMEOUT
        elif isinstance(timeout, (int, float)):
            self._timeout = httpx.Timeout(timeout)
        else:
            self._timeout = timeout

        self._max_retries = max_retries
        self._custom_headers = dict(default_headers) if default_headers else {}

    @property
    def _site_root(self) -> str:
        """Scheme + host of the base URL — for site-root endpoints (/auth/*, /health)."""
        parsed = urlparse(self._base_url)
        return f"{parsed.scheme}://{parsed.netloc}"
