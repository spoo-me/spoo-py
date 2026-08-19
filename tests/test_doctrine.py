"""Regression tests for the 2026-08 SDK doctrine backport."""

from __future__ import annotations

import httpx
import pytest

from spoo import AsyncSpooClient, NotFoundError, SpooClient
from spoo._resources.stats import _sanitize_filename

ITEM = {"id": "a" * 24, "alias": "mylink", "password_set": False}


def test_filename_sanitization_pure():
    assert _sanitize_filename("mylink stats.csv") == "mylink stats.csv"
    assert _sanitize_filename("../../../evil.json") == "evil.json"
    assert _sanitize_filename("/tmp/absolute-evil.json") == "absolute-evil.json"
    assert _sanitize_filename("..\\..\\win-evil.xlsx") == "win-evil.xlsx"
    assert _sanitize_filename("..") is None
    assert _sanitize_filename(".") is None
    assert _sanitize_filename("") is None
    assert _sanitize_filename(None) is None
    assert _sanitize_filename("a/../") is None


@pytest.mark.asyncio
async def test_hostile_disposition_reduced_to_basename(mock_api, async_client):
    mock_api.get("/export").mock(
        return_value=httpx.Response(
            200,
            content=b"x",
            headers={
                "Content-Disposition": "attachment; filename*=utf-8''%2e%2e%2f%2e%2e%2fesc.json"
            },
        )
    )
    data = await async_client.stats.export("json")
    assert data.filename == "esc.json"  # never "../../esc.json"


def test_injected_http_client_is_used_and_not_closed():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=ITEM)

    injected = httpx.Client(transport=httpx.MockTransport(handler))
    with SpooClient(api_key="spoo_test", http_client=injected) as client:
        client.urls.get("a" * 24)
    assert seen == [f"https://spoo.me/api/v1/urls/{'a' * 24}"]
    assert not injected.is_closed  # caller owns it; the SDK must not close it
    injected.close()


def test_escape_hatch_request(mock_api, sync_client):
    mock_api.get("/urls").mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
    body = sync_client.request("GET", "/urls", params={"page": 1})
    assert body == {"items": [], "total": 0}

    mock_api.get("/nope").mock(return_value=httpx.Response(404, json={"error": "missing"}))
    with pytest.raises(NotFoundError):  # error mapping still applies
        sync_client.request("GET", "/nope")


@pytest.mark.asyncio
async def test_escape_hatch_async(mock_api, async_client):
    mock_api.post("/urls/bulk/delete").mock(
        return_value=httpx.Response(200, json={"summary": {"total": 0}})
    )
    body = await async_client.request("POST", "/urls/bulk/delete", json={"ids": []})
    assert body["summary"]["total"] == 0


@pytest.mark.asyncio
async def test_async_injected_client():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ITEM)

    injected = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with AsyncSpooClient(api_key="spoo_test", http_client=injected) as client:
        item = await client.urls.get("a" * 24)
        assert item.alias == "mylink"
    assert not injected.is_closed
    await injected.aclose()
