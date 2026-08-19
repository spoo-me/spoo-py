from __future__ import annotations

import httpx
import pytest

from spoo import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


@pytest.mark.asyncio
async def test_400_validation_error(mock_api, async_client):
    mock_api.post("/shorten").mock(
        return_value=httpx.Response(
            400,
            json={"error": "Invalid URL", "code": "validation_error", "field": "long_url"},
        )
    )
    with pytest.raises(ValidationError) as exc_info:
        await async_client.urls.create("https://example.com/bad")
    assert exc_info.value.status_code == 400
    assert exc_info.value.field == "long_url"
    assert exc_info.value.error_code == "validation_error"


@pytest.mark.asyncio
async def test_422_fastapi_validation(mock_api, async_client):
    mock_api.post("/shorten").mock(
        return_value=httpx.Response(
            422,
            json={
                "detail": [
                    {"loc": ["body", "long_url"], "msg": "field required", "type": "missing"}
                ]
            },
        )
    )
    with pytest.raises(ValidationError) as exc_info:
        await async_client.urls.create("https://example.com/test")
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_401_authentication_error(mock_api, async_client):
    mock_api.get("/urls").mock(
        return_value=httpx.Response(
            401, json={"error": "Invalid token", "error_code": "authentication_error"}
        )
    )
    with pytest.raises(AuthenticationError):
        await async_client.urls.list_page()


@pytest.mark.asyncio
async def test_403_forbidden(mock_api, async_client):
    mock_api.get("/urls").mock(
        return_value=httpx.Response(403, json={"error": "Insufficient scope", "code": "forbidden"})
    )
    with pytest.raises(ForbiddenError):
        await async_client.urls.list_page()


@pytest.mark.asyncio
async def test_404_not_found(mock_api, async_client):
    mock_api.delete("/urls/nonexistent").mock(
        return_value=httpx.Response(404, json={"error": "URL not found", "code": "not_found"})
    )
    with pytest.raises(NotFoundError):
        await async_client.urls.delete("nonexistent")


@pytest.mark.asyncio
async def test_409_conflict(mock_api, async_client):
    mock_api.post("/shorten").mock(
        return_value=httpx.Response(409, json={"error": "Alias already taken", "code": "conflict"})
    )
    with pytest.raises(ConflictError):
        await async_client.urls.create("https://example.com", alias="taken-alias")


@pytest.mark.asyncio
async def test_429_rate_limit(mock_api, async_client):
    async_client._transport._max_retries = 0
    mock_api.post("/shorten").mock(
        return_value=httpx.Response(
            429,
            json={"error": "Rate limit exceeded", "code": "rate_limit_exceeded"},
            headers={"Retry-After": "30"},
        )
    )
    with pytest.raises(RateLimitError) as exc_info:
        await async_client.urls.create("https://example.com")
    assert exc_info.value.retry_after == 30.0


@pytest.mark.asyncio
async def test_error_code_parsed_from_both_fields(mock_api, async_client):
    mock_api.post("/shorten").mock(
        return_value=httpx.Response(400, json={"error": "Bad", "code": "validation_error"})
    )
    with pytest.raises(ValidationError) as exc_info:
        await async_client.urls.create("https://example.com/bad-request")
    assert exc_info.value.error_code == "validation_error"


# ── Client-side validation tests ─────────────────────────────────────────


def test_validate_url_rejects_bad_scheme():
    from spoo._validators import validate_url

    with pytest.raises(ValueError, match="http:// or https://"):
        validate_url("ftp://example.com")


def test_validate_url_rejects_empty():
    from spoo._validators import validate_url

    with pytest.raises(ValueError):
        validate_url("")


def test_validate_alias_rejects_short():
    from spoo._validators import validate_alias

    with pytest.raises(ValueError, match="3-16 characters"):
        validate_alias("ab")


def test_validate_alias_rejects_special_chars():
    from spoo._validators import validate_alias

    with pytest.raises(ValueError):
        validate_alias("my link!")


def test_validate_password_rejects_short():
    from spoo._validators import validate_password

    with pytest.raises(ValueError, match="at least 8"):
        validate_password("short")


def test_validate_password_rejects_no_digit():
    from spoo._validators import validate_password

    with pytest.raises(ValueError, match="digit"):
        validate_password("NoDigits@Here")


def test_validate_password_rejects_no_special():
    from spoo._validators import validate_password

    with pytest.raises(ValueError, match="special"):
        validate_password("NoSpecial123")


def test_validate_max_clicks_rejects_zero():
    from spoo._validators import validate_max_clicks

    with pytest.raises(ValueError, match="positive"):
        validate_max_clicks(0)


def test_validate_max_clicks_rejects_negative():
    from spoo._validators import validate_max_clicks

    with pytest.raises(ValueError, match="positive"):
        validate_max_clicks(-5)


def test_client_side_validation_before_http(async_client):
    """Validation fires before any HTTP call — no mock needed."""
    with pytest.raises(ValueError, match="http://"):
        import asyncio

        asyncio.get_event_loop().run_until_complete(async_client.urls.create("not-a-url"))
