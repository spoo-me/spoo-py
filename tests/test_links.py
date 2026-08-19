from __future__ import annotations

import httpx
import pytest

from spoo import CreatedLink, DeletedLink, LinkPage, UpdatedLink

BASE_URL = "https://spoo.me/api/v1"

SHORTEN_RESPONSE = {
    "alias": "mylink",
    "short_url": "https://spoo.me/mylink",
    "long_url": "https://example.com/long",
    "owner_id": "507f1f77bcf86cd799439011",
    "created_at": 1704067200,
    "status": "ACTIVE",
    "private_stats": False,
}

LIST_RESPONSE = {
    "items": [
        {
            "id": "abc123",
            "alias": "mylink",
            "long_url": "https://example.com",
            "status": "ACTIVE",
            "created_at": "2024-01-01T00:00:00Z",
            "password_set": False,
            "total_clicks": 42,
        }
    ],
    "page": 1,
    "pageSize": 20,
    "total": 1,
    "hasNext": False,
    "sortBy": "created_at",
    "sortOrder": "descending",
}

UPDATE_RESPONSE = {
    "id": "abc123",
    "alias": "newlink",
    "long_url": "https://example.com/updated",
    "status": "ACTIVE",
    "password_set": False,
    "updated_at": 1704067300,
}

DELETE_RESPONSE = {
    "message": "URL deleted",
    "id": "abc123",
}


@pytest.mark.asyncio
async def test_create_url(mock_api, async_client):
    mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN_RESPONSE))
    url = await async_client.links.create("https://example.com/long", alias="mylink")
    assert isinstance(url, CreatedLink)
    assert url.alias == "mylink"
    assert url.short_url == "https://spoo.me/mylink"
    assert url.created_at == 1704067200


@pytest.mark.asyncio
async def test_create_url_with_all_params(mock_api, async_client):
    mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN_RESPONSE))
    url = await async_client.links.create(
        "https://example.com/long",
        alias="mylink",
        password="Secure@123",
        block_bots=True,
        max_clicks=100,
        expire_after="2025-12-31T23:59:59Z",
        private_stats=True,
    )
    assert url.alias == "mylink"
    req = mock_api.calls[0].request
    import json

    body = json.loads(req.content)
    assert body["password"] == "Secure@123"
    assert body["block_bots"] is True
    assert body["max_clicks"] == 100


@pytest.mark.asyncio
async def test_shorten_convenience(mock_api, async_client):
    mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN_RESPONSE))
    url = await async_client.shorten("https://example.com/long", alias="mylink")
    assert url.alias == "mylink"


@pytest.mark.asyncio
async def test_list_page(mock_api, async_client):
    mock_api.get("/urls").mock(return_value=httpx.Response(200, json=LIST_RESPONSE))
    page = await async_client.links.list_page()
    assert isinstance(page, LinkPage)
    assert len(page.items) == 1
    assert page.items[0].alias == "mylink"
    assert page.total == 1
    assert page.hasNext is False


@pytest.mark.asyncio
async def test_list_auto_paginate(mock_api, async_client):
    mock_api.get("/urls").mock(return_value=httpx.Response(200, json=LIST_RESPONSE))
    items = []
    async for url in async_client.links.list():
        items.append(url)
    assert len(items) == 1
    assert items[0].alias == "mylink"


@pytest.mark.asyncio
async def test_update_url(mock_api, async_client):
    mock_api.patch("/urls/abc123").mock(return_value=httpx.Response(200, json=UPDATE_RESPONSE))
    result = await async_client.links.update(
        "abc123", long_url="https://example.com/updated", alias="newlink"
    )
    assert isinstance(result, UpdatedLink)
    assert result.alias == "newlink"


@pytest.mark.asyncio
async def test_set_status(mock_api, async_client):
    mock_api.patch("/urls/abc123/status").mock(
        return_value=httpx.Response(200, json=UPDATE_RESPONSE)
    )
    result = await async_client.links.set_status("abc123", "ACTIVE")
    assert isinstance(result, UpdatedLink)


@pytest.mark.asyncio
async def test_delete_url(mock_api, async_client):
    mock_api.delete("/urls/abc123").mock(return_value=httpx.Response(200, json=DELETE_RESPONSE))
    result = await async_client.links.delete("abc123")
    assert isinstance(result, DeletedLink)
    assert result.id == "abc123"


def test_url_filter_serializes_enum_status():
    from spoo import LinkFilter, LinkStatus

    assert LinkFilter(status=LinkStatus.ACTIVE).to_dict() == {"status": "ACTIVE"}
    assert LinkFilter(status="INACTIVE").to_dict() == {"status": "INACTIVE"}


@pytest.mark.asyncio
async def test_list_honors_start_page(mock_api, async_client):
    page2 = {**LIST_RESPONSE, "page": 2}
    mock_api.get("/urls").mock(return_value=httpx.Response(200, json=page2))
    items = [url async for url in async_client.links.list(page=2)]
    assert len(items) == 1
    assert "page=2" in str(mock_api.calls[0].request.url)


@pytest.mark.asyncio
async def test_shorten_convenience_full_params(mock_api, async_client):
    mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN_RESPONSE))
    await async_client.shorten("https://example.com/long", block_bots=True, private_stats=True)
    import json

    body = json.loads(mock_api.calls[0].request.content)
    assert body["block_bots"] is True
    assert body["private_stats"] is True


@pytest.mark.asyncio
async def test_create_with_custom_domain(mock_api, async_client):
    mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN_RESPONSE))
    await async_client.links.create("https://example.com", domain="links.acme.com")
    import json

    body = json.loads(mock_api.calls[0].request.content)
    assert body["domain"] == "links.acme.com"


@pytest.mark.asyncio
async def test_check_alias(mock_api, async_client):
    from spoo import AliasCheck

    mock_api.get("/shorten/check-alias").mock(
        return_value=httpx.Response(200, json={"available": False, "reason": "taken"})
    )
    result = await async_client.links.check_alias("mylink", domain="links.acme.com")
    assert isinstance(result, AliasCheck)
    assert result.available is False
    assert result.reason == "taken"
    url = str(mock_api.calls[0].request.url)
    assert "alias=mylink" in url
    assert "domain=links.acme.com" in url


@pytest.mark.asyncio
async def test_delete_all_by_domain(mock_api, async_client):
    from spoo import BulkDeletedLinks

    mock_api.delete("/urls").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": "deleted 42 URLs on links.acme.com",
                "count": 42,
                "domain": "links.acme.com",
            },
        )
    )
    result = await async_client.links.delete_all("links.acme.com")
    assert isinstance(result, BulkDeletedLinks)
    assert result.count == 42
    assert "domain=links.acme.com" in str(mock_api.calls[0].request.url)


@pytest.mark.asyncio
async def test_list_page_domain_param(mock_api, async_client):
    mock_api.get("/urls").mock(return_value=httpx.Response(200, json=LIST_RESPONSE))
    await async_client.links.list_page(domain="links.acme.com")
    assert "domain=links.acme.com" in str(mock_api.calls[0].request.url)


@pytest.mark.asyncio
async def test_client_tag_header_sent(mock_api, async_client):
    mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN_RESPONSE))
    await async_client.shorten("https://example.com/long")
    from spoo._constants import CLIENT_TAG

    assert mock_api.calls[0].request.headers["X-Spoo-Client"] == CLIENT_TAG
