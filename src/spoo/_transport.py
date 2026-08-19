from __future__ import annotations

import random
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from ._auth import AuthStrategy, DynamicBearerAuth
from ._constants import (
    CLIENT_TAG,
    INITIAL_RETRY_DELAY,
    MAX_RETRY_DELAY,
    NONIDEMPOTENT_RETRYABLE_STATUS_CODES,
    RETRYABLE_STATUS_CODES,
    USER_AGENT,
)
from ._errors import (
    APIConnectionError,
    APITimeoutError,
    parse_retry_after,
    raise_for_status,
)

T = TypeVar("T", bound=BaseModel)

_IDEMPOTENT_METHODS = frozenset({"GET", "PUT", "DELETE"})


def _json_or_text(response: httpx.Response) -> Any:
    """Parsed JSON, the raw text for non-JSON bodies, or None when empty.

    The escape hatch can hit anything; a non-JSON 200 must not raise
    outside the SDK's error types.
    """
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


class BaseTransport:
    """Shared logic for both sync and async transports: headers, retry delay, response parsing."""

    def __init__(
        self,
        *,
        base_url: str,
        auth: AuthStrategy,
        max_retries: int,
        custom_headers: dict[str, str],
    ) -> None:
        self._base_url = base_url
        self._auth = auth
        self._max_retries = max_retries
        self._custom_headers = custom_headers
        self._owns_client = True

    def _url(self, path: str) -> str:
        if "://" in path:
            return path
        return f"{self._base_url.rstrip('/')}{path}"

    def _build_headers(
        self, *, with_json: bool = False, authenticated: bool = True
    ) -> dict[str, str]:
        headers: dict[str, str] = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "X-Spoo-Client": CLIENT_TAG,
        }
        if with_json:
            headers["Content-Type"] = "application/json"
        headers.update(self._custom_headers)
        if not authenticated:
            headers.pop("Authorization", None)
            return headers
        return self._auth.apply(headers)

    @staticmethod
    def _clean_params(params: dict[str, Any] | None) -> dict[str, Any] | None:
        if params:
            return {k: v for k, v in params.items() if v is not None}
        return params

    @staticmethod
    def _parse_response(response: httpx.Response, cast_to: type[T]) -> T:
        return cast_to.model_validate(response.json())

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        base = min(INITIAL_RETRY_DELAY * (2**attempt), MAX_RETRY_DELAY)
        return float(base * (0.5 + random.random() * 0.5))  # noqa: S311

    def _should_retry(
        self, response: httpx.Response, attempt: int, method: str, retries: int
    ) -> bool:
        if attempt >= retries:
            return False
        if method in _IDEMPOTENT_METHODS:
            return response.status_code in RETRYABLE_STATUS_CODES
        # Non-idempotent: retry only when the server provably did no work.
        return response.status_code in NONIDEMPOTENT_RETRYABLE_STATUS_CODES

    @staticmethod
    def _should_retry_connection(method: str, attempt: int, retries: int) -> bool:
        return method in _IDEMPOTENT_METHODS and attempt < retries

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        if response.status_code == 429:
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            if retry_after is not None:
                return retry_after
        return self._backoff_delay(attempt)


class AsyncTransport(BaseTransport):
    """Async HTTP transport using httpx.AsyncClient."""

    def __init__(
        self,
        *,
        timeout: httpx.Timeout,
        http_client: httpx.AsyncClient | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if http_client is not None:
            self._client = http_client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(timeout=timeout)

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        cast_to: type[T],
        authenticated: bool = True,
        retries: int | None = None,
    ) -> T:
        response = await self._send_with_retry(
            method, path, json=json, params=params, authenticated=authenticated, retries=retries
        )
        return self._parse_response(response, cast_to)

    async def request_raw(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return await self._send_with_retry(method, path, params=params)

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        response = await self._send_with_retry(method, path, json=json, params=params)
        return _json_or_text(response)

    async def _resolve_auth(self, headers: dict[str, str]) -> dict[str, str]:
        if isinstance(self._auth, DynamicBearerAuth) and "Authorization" not in headers:
            token = self._auth.provider()  # type: ignore[operator]
            if hasattr(token, "__await__"):
                token = await token
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _send_with_retry(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        authenticated: bool = True,
        retries: int | None = None,
    ) -> httpx.Response:
        import asyncio

        max_retries = self._max_retries if retries is None else retries
        params = self._clean_params(params)

        for attempt in range(max_retries + 1):
            headers = self._build_headers(with_json=json is not None, authenticated=authenticated)
            if authenticated:
                headers = await self._resolve_auth(headers)
            try:
                response = await self._client.request(
                    method, self._url(path), headers=headers, json=json, params=params
                )
            except httpx.TimeoutException as exc:
                if self._should_retry_connection(method, attempt, max_retries):
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue
                raise APITimeoutError(f"Request timed out: {exc}") from exc
            except httpx.ConnectError as exc:
                if self._should_retry_connection(method, attempt, max_retries):
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue
                raise APIConnectionError(f"Connection failed: {exc}") from exc

            if response.status_code < 400:
                return response

            if not self._should_retry(response, attempt, method, max_retries):
                raise_for_status(response)

            await asyncio.sleep(self._retry_delay(response, attempt))

        raise_for_status(response)
        raise AssertionError("unreachable")  # pragma: no cover

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class SyncTransport(BaseTransport):
    """Sync HTTP transport using httpx.Client. No background threads needed."""

    def __init__(
        self,
        *,
        timeout: httpx.Timeout,
        http_client: httpx.Client | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if http_client is not None:
            self._client = http_client
            self._owns_client = False
        else:
            self._client = httpx.Client(timeout=timeout)

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        cast_to: type[T],
        authenticated: bool = True,
        retries: int | None = None,
    ) -> T:
        response = self._send_with_retry(
            method, path, json=json, params=params, authenticated=authenticated, retries=retries
        )
        return self._parse_response(response, cast_to)

    def request_raw(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return self._send_with_retry(method, path, params=params)

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        response = self._send_with_retry(method, path, json=json, params=params)
        return _json_or_text(response)

    def _resolve_auth(self, headers: dict[str, str]) -> dict[str, str]:
        if isinstance(self._auth, DynamicBearerAuth) and "Authorization" not in headers:
            token = self._auth.provider()  # type: ignore[operator]
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _send_with_retry(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        authenticated: bool = True,
        retries: int | None = None,
    ) -> httpx.Response:
        import time

        max_retries = self._max_retries if retries is None else retries
        params = self._clean_params(params)

        for attempt in range(max_retries + 1):
            headers = self._build_headers(with_json=json is not None, authenticated=authenticated)
            if authenticated:
                headers = self._resolve_auth(headers)
            try:
                response = self._client.request(
                    method, self._url(path), headers=headers, json=json, params=params
                )
            except httpx.TimeoutException as exc:
                if self._should_retry_connection(method, attempt, max_retries):
                    time.sleep(self._backoff_delay(attempt))
                    continue
                raise APITimeoutError(f"Request timed out: {exc}") from exc
            except httpx.ConnectError as exc:
                if self._should_retry_connection(method, attempt, max_retries):
                    time.sleep(self._backoff_delay(attempt))
                    continue
                raise APIConnectionError(f"Connection failed: {exc}") from exc

            if response.status_code < 400:
                return response

            if not self._should_retry(response, attempt, method, max_retries):
                raise_for_status(response)

            time.sleep(self._retry_delay(response, attempt))

        raise_for_status(response)
        raise AssertionError("unreachable")  # pragma: no cover

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
