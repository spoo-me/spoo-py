"""Retry policy and rate-limit header behavior."""

from __future__ import annotations

import httpx
import pytest

from spoo import InternalServerError, RateLimitError

RESP_429 = httpx.Response(
    429,
    json={"error": "Too many requests", "code": "rate_limit_exceeded"},
    headers={
        "Retry-After": "0",
        "X-RateLimit-Limit": "5",
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": "1755600000",
    },
)


@pytest.mark.asyncio
async def test_rate_limit_error_carries_headers(mock_api, async_client):
    mock_api.get("/urls/abc").mock(return_value=RESP_429)
    with pytest.raises(RateLimitError) as exc_info:
        await async_client.urls.get("abc")
    err = exc_info.value
    assert err.retry_after == 0.0
    assert err.limit == 5
    assert err.remaining == 0
    assert err.reset == 1755600000


@pytest.mark.asyncio
async def test_get_retries_on_500(mock_api, async_client):
    route = mock_api.get("/urls/abc").mock(
        side_effect=[
            httpx.Response(500, json={"error": "boom"}),
            httpx.Response(200, json={"id": "abc", "password_set": False}),
        ]
    )
    item = await async_client.urls.get("abc")
    assert item.id == "abc"
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_post_does_not_retry_on_500(mock_api, async_client):
    route = mock_api.post("/shorten").mock(return_value=httpx.Response(500, json={"error": "x"}))
    with pytest.raises(InternalServerError):
        await async_client.urls.create("https://example.com")
    assert route.call_count == 1  # non-idempotent: the server may have done work


@pytest.mark.asyncio
async def test_post_retries_on_429(mock_api, async_client):
    route = mock_api.post("/shorten").mock(
        side_effect=[
            RESP_429,
            httpx.Response(
                201,
                json={
                    "alias": "x",
                    "short_url": "https://spoo.me/x",
                    "long_url": "https://example.com",
                    "created_at": 1,
                    "status": "ACTIVE",
                },
            ),
        ]
    )
    url = await async_client.urls.create("https://example.com")
    assert url.alias == "x"
    assert route.call_count == 2
