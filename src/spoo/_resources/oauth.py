"""Sign in with Spoo: the PKCE device-auth flow for connected apps.

The flow (all endpoints live at the site root, not under /api/v1):

1. ``generate_pkce()`` + ``generate_state()``, persist both.
2. Send the user to ``authorization_url(...)`` in a browser.
3. Your redirect URI receives ``code`` (verify ``state`` yourself).
4. ``exchange_code(code, verifier)`` -> access + refresh tokens.
5. Build a client with ``token_provider(...)`` so refresh happens for you.

Refresh tokens rotate: every refresh invalidates the pair it was made from,
so persist the newest pair from ``on_refresh``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlencode

from .._errors import APIError, SessionExpiredError
from .._pkce import PkcePair, decode_jwt_payload, generate_pkce_pair, generate_state
from .._transport import AsyncTransport, SyncTransport
from ..types.oauth import OAuthTokens

__all__ = ["AsyncOAuth", "OAuth"]

_ON_REFRESH_SYNC = Callable[[OAuthTokens], None]
_ON_REFRESH_ASYNC = Callable[[OAuthTokens], Any]


def _access_expiry(access_token: str) -> float | None:
    payload = decode_jwt_payload(access_token)
    exp = payload.get("exp") if payload else None
    return float(exp) if isinstance(exp, (int, float)) else None


class _OAuthShared:
    """URL building and PKCE helpers, identical for sync and async."""

    def __init__(self, site_root: str) -> None:
        self._site_root = site_root.rstrip("/")

    @staticmethod
    def generate_pkce() -> PkcePair:
        """A fresh S256 (verifier, challenge) pair."""
        return generate_pkce_pair()

    @staticmethod
    def generate_state() -> str:
        """An unguessable state value for CSRF protection."""
        return generate_state()

    def authorization_url(
        self,
        app_id: str,
        *,
        code_challenge: str,
        state: str,
        redirect_uri: str | None = None,
    ) -> str:
        """The consent-page URL to open in the user's browser.

        ``redirect_uri`` must exactly match a URI registered for the app
        (port included); omit it to use the app's registered default.
        """
        params = {"app_id": app_id, "state": state, "code_challenge": code_challenge}
        if redirect_uri is not None:
            params["redirect_uri"] = redirect_uri
        params["code_challenge_method"] = "S256"
        return f"{self._site_root}/auth/device/login?{urlencode(params)}"


class OAuth(_OAuthShared):
    """Sign in with Spoo (sync)."""

    def __init__(self, transport: SyncTransport, site_root: str) -> None:
        super().__init__(site_root)
        self._transport = transport

    def exchange_code(self, code: str, code_verifier: str) -> OAuthTokens:
        """Exchange the callback code for a token pair. No auth header: the
        code plus verifier are the credentials."""
        return self._transport.request(
            "POST",
            f"{self._site_root}/auth/device/token",
            json={"code": code, "code_verifier": code_verifier},
            cast_to=OAuthTokens,
            authenticated=False,
        )

    def refresh_tokens(self, refresh_token: str) -> OAuthTokens:
        """Rotate the token pair. Raises SessionExpiredError when the refresh
        token is no longer accepted (the user must sign in again)."""
        try:
            return self._transport.request(
                "POST",
                f"{self._site_root}/auth/device/refresh",
                json={"refresh_token": refresh_token},
                cast_to=OAuthTokens,
                authenticated=False,
            )
        except APIError as exc:
            if exc.status_code in (400, 401):
                raise SessionExpiredError("Refresh token rejected; sign in again") from exc
            raise

    def token_provider(
        self,
        tokens: OAuthTokens,
        *,
        on_refresh: _ON_REFRESH_SYNC | None = None,
        expiry_skew: float = 30.0,
    ) -> SyncTokenProvider:
        """A callable for ``SpooClient(bearer_token=...)`` that serves the
        current access token and refreshes it before expiry."""
        return SyncTokenProvider(self, tokens, on_refresh=on_refresh, expiry_skew=expiry_skew)


class AsyncOAuth(_OAuthShared):
    """Sign in with Spoo (async)."""

    def __init__(self, transport: AsyncTransport, site_root: str) -> None:
        super().__init__(site_root)
        self._transport = transport

    async def exchange_code(self, code: str, code_verifier: str) -> OAuthTokens:
        """Exchange the callback code for a token pair. No auth header: the
        code plus verifier are the credentials."""
        return await self._transport.request(
            "POST",
            f"{self._site_root}/auth/device/token",
            json={"code": code, "code_verifier": code_verifier},
            cast_to=OAuthTokens,
            authenticated=False,
        )

    async def refresh_tokens(self, refresh_token: str) -> OAuthTokens:
        """Rotate the token pair. Raises SessionExpiredError when the refresh
        token is no longer accepted (the user must sign in again)."""
        try:
            return await self._transport.request(
                "POST",
                f"{self._site_root}/auth/device/refresh",
                json={"refresh_token": refresh_token},
                cast_to=OAuthTokens,
                authenticated=False,
            )
        except APIError as exc:
            if exc.status_code in (400, 401):
                raise SessionExpiredError("Refresh token rejected; sign in again") from exc
            raise

    def token_provider(
        self,
        tokens: OAuthTokens,
        *,
        on_refresh: _ON_REFRESH_ASYNC | None = None,
        expiry_skew: float = 30.0,
    ) -> AsyncTokenProvider:
        """A callable for ``AsyncSpooClient(bearer_token=...)`` that serves
        the current access token and refreshes it before expiry."""
        return AsyncTokenProvider(self, tokens, on_refresh=on_refresh, expiry_skew=expiry_skew)


class SyncTokenProvider:
    """Serves the current access token; refreshes single-flight before expiry.

    An unparseable access-token expiry means never refresh proactively; call
    ``invalidate()`` (e.g. after a 401) to force a refresh on the next request.
    """

    def __init__(
        self,
        oauth: OAuth,
        tokens: OAuthTokens,
        *,
        on_refresh: _ON_REFRESH_SYNC | None,
        expiry_skew: float,
    ) -> None:
        self._oauth = oauth
        self._tokens = tokens
        self._on_refresh = on_refresh
        self._skew = expiry_skew
        self._expires_at = _access_expiry(tokens.access_token)
        self._stale = False
        self._lock = threading.Lock()

    @property
    def tokens(self) -> OAuthTokens:
        """The current pair — persist this if you outlive the process."""
        return self._tokens

    def invalidate(self) -> None:
        """Force a refresh before the next request (e.g. after a 401)."""
        self._stale = True

    def _fresh(self) -> bool:
        if self._stale:
            return False
        if self._expires_at is None:
            return True
        return time.time() < self._expires_at - self._skew

    def __call__(self) -> str:
        if self._fresh():
            return self._tokens.access_token
        with self._lock:
            if self._fresh():  # another caller refreshed while we waited
                return self._tokens.access_token
            rotated = self._oauth.refresh_tokens(self._tokens.refresh_token)
            self._tokens = rotated
            self._expires_at = _access_expiry(rotated.access_token)
            self._stale = False
            if self._on_refresh is not None:
                self._on_refresh(rotated)
        return self._tokens.access_token


class AsyncTokenProvider:
    """Async twin of :class:`SyncTokenProvider`."""

    def __init__(
        self,
        oauth: AsyncOAuth,
        tokens: OAuthTokens,
        *,
        on_refresh: _ON_REFRESH_ASYNC | None,
        expiry_skew: float,
    ) -> None:
        self._oauth = oauth
        self._tokens = tokens
        self._on_refresh = on_refresh
        self._skew = expiry_skew
        self._expires_at = _access_expiry(tokens.access_token)
        self._stale = False
        self._lock: Any = None  # created lazily inside a running loop

    @property
    def tokens(self) -> OAuthTokens:
        """The current pair — persist this if you outlive the process."""
        return self._tokens

    def invalidate(self) -> None:
        """Force a refresh before the next request (e.g. after a 401)."""
        self._stale = True

    def _fresh(self) -> bool:
        if self._stale:
            return False
        if self._expires_at is None:
            return True
        return time.time() < self._expires_at - self._skew

    async def __call__(self) -> str:
        import asyncio

        if self._fresh():
            return self._tokens.access_token
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if self._fresh():  # another task refreshed while we waited
                return self._tokens.access_token
            rotated = await self._oauth.refresh_tokens(self._tokens.refresh_token)
            self._tokens = rotated
            self._expires_at = _access_expiry(rotated.access_token)
            self._stale = False
            if self._on_refresh is not None:
                result = self._on_refresh(rotated)
                if isinstance(result, Awaitable):
                    await result
        return self._tokens.access_token
