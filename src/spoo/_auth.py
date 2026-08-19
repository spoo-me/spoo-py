from __future__ import annotations

from typing import Protocol


class AuthStrategy(Protocol):
    def apply(self, headers: dict[str, str]) -> dict[str, str]: ...


class ApiKeyAuth:
    """Adds ``Authorization: Bearer spoo_<token>`` header."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def apply(self, headers: dict[str, str]) -> dict[str, str]:
        headers["Authorization"] = f"Bearer {self._api_key}"
        return headers


class BearerTokenAuth:
    """Adds ``Authorization: Bearer <jwt>`` header."""

    def __init__(self, token: str) -> None:
        self._token = token

    def apply(self, headers: dict[str, str]) -> dict[str, str]:
        headers["Authorization"] = f"Bearer {self._token}"
        return headers


class NoAuth:
    """Anonymous — no auth header."""

    def apply(self, headers: dict[str, str]) -> dict[str, str]:
        return headers


class DynamicBearerAuth:
    """Bearer auth from a callable, resolved per request by the transport.

    ``provider`` returns the current access token; async clients may pass a
    provider whose result is awaitable. The transports resolve it before
    every send (retries included), so a provider that refreshes expired
    tokens keeps long-lived clients authenticated transparently.
    """

    def __init__(self, provider: object) -> None:
        self.provider = provider

    def apply(self, headers: dict[str, str]) -> dict[str, str]:
        return headers  # resolved per request in the transports
