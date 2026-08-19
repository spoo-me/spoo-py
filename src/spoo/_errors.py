from __future__ import annotations

from typing import Any

import httpx


class SpooError(Exception):
    """Base for all SDK errors."""

    message: str

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class APIError(SpooError):
    """Base for errors returned by the spoo.me API."""

    status_code: int
    error_code: str | None
    field: str | None
    details: Any
    body: dict[str, Any] | None

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        if body:
            self.error_code = body.get("error_code") or body.get("code")
            self.field = body.get("field")
            self.details = body.get("details") or body.get("detail")
        else:
            self.error_code = None
            self.field = None
            self.details = None

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(message={self.message!r}, "
            f"status_code={self.status_code}, error_code={self.error_code!r})"
        )


class ValidationError(APIError):
    """400 Bad Request or 422 Validation Error."""


class AuthenticationError(APIError):
    """401 Unauthorized."""


class ForbiddenError(APIError):
    """403 Forbidden."""


class NotFoundError(APIError):
    """404 Not Found."""


class ConflictError(APIError):
    """409 Conflict (e.g., alias already taken)."""


class GoneError(APIError):
    """410 Gone (expired URL)."""


class RateLimitError(APIError):
    """429 Rate Limit Exceeded.

    ``limit``, ``remaining``, and ``reset`` mirror the X-RateLimit-* headers
    when the server sends them: the evaluated window size, requests left in
    it, and the window reset as an epoch timestamp.
    """

    retry_after: float | None
    limit: int | None
    remaining: int | None
    reset: int | None

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        body: dict[str, Any] | None = None,
        retry_after: float | None = None,
        limit: int | None = None,
        remaining: int | None = None,
        reset: int | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, body=body)
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        self.reset = reset


class InternalServerError(APIError):
    """5xx Server Error."""


class APIConnectionError(SpooError):
    """Network-level failure (DNS, connection refused, etc.)."""


class APITimeoutError(APIConnectionError):
    """Request timed out."""


class SessionExpiredError(SpooError):
    """The refresh token was rejected — the user must sign in again.

    Deliberately outside the APIError tree: this is a session-lifecycle
    outcome, not a request failure to retry or map by status code.
    """


ERROR_MAP: dict[int, type[APIError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    410: GoneError,
    422: ValidationError,
    429: RateLimitError,
}


def _int_header(response: httpx.Response, name: str) -> int | None:
    raw = response.headers.get(name)
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def raise_for_status(response: httpx.Response) -> None:
    """Map an HTTP error response to a typed SDK exception. (SRP: owned by errors module.)"""
    body: dict[str, Any] | None = None
    message = f"Error {response.status_code}"

    try:
        body = response.json()
        message = body.get("error", message)
    except Exception:
        message = response.text or message

    error_cls = ERROR_MAP.get(response.status_code)
    if error_cls is None:
        error_cls = InternalServerError if response.status_code >= 500 else APIError

    if error_cls is RateLimitError:
        retry_after_str = response.headers.get("Retry-After")
        retry_after = float(retry_after_str) if retry_after_str else None
        raise RateLimitError(
            message,
            status_code=response.status_code,
            body=body,
            retry_after=retry_after,
            limit=_int_header(response, "X-RateLimit-Limit"),
            remaining=_int_header(response, "X-RateLimit-Remaining"),
            reset=_int_header(response, "X-RateLimit-Reset"),
        )

    raise error_cls(message, status_code=response.status_code, body=body)
