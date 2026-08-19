"""Tests for the v2.1.x URL surface: claim, bulk, single GETs, emoji aliases."""

from __future__ import annotations

import json

import httpx
import pytest

from spoo import AliasType, BulkResult, ClaimedLinks, EmojiSet, Link
from spoo._validators import canonicalize_emoji, validate_emoji_alias

ITEM = {"id": "a" * 24, "alias": "mylink", "password_set": False}
SHORTEN = {
    "alias": "mylink",
    "short_url": "https://spoo.me/mylink",
    "long_url": "https://example.com",
    "created_at": 1704067200,
    "status": "ACTIVE",
}
EMOJI_SET = {
    "accept_max_version": 15.1,
    "generate_max_version": 12.0,
    "max_graphemes": 3,
    "emoji": [
        {"c": "🚀", "n": "rocket", "g": "Travel & Places", "gen": True},
        {"c": "🔥", "n": "fire", "g": "Smileys & Emotion", "gen": True},
    ],
}
BULK_OK = {
    "summary": {"total": 2, "succeeded": 2, "failed": 0},
    "results": [
        {"id": "a" * 24, "ok": True},
        {"id": "b" * 24, "ok": True},
    ],
}


@pytest.mark.asyncio
async def test_get_by_id(mock_api, async_client):
    mock_api.get(f"/urls/{'a' * 24}").mock(return_value=httpx.Response(200, json=ITEM))
    item = await async_client.links.get("a" * 24)
    assert isinstance(item, Link)
    assert item.alias == "mylink"


@pytest.mark.asyncio
async def test_get_by_alias_defaults_domain_from_base_url(mock_api, async_client):
    mock_api.get("/urls/spoo.me/mylink").mock(return_value=httpx.Response(200, json=ITEM))
    item = await async_client.links.get_by_alias("mylink")
    assert item.id == "a" * 24

    mock_api.get("/urls/links.acme.com/mylink").mock(return_value=httpx.Response(200, json=ITEM))
    await async_client.links.get_by_alias("mylink", domain="links.acme.com")


@pytest.mark.asyncio
async def test_claim_single_sends_token_field(mock_api, async_client):
    route = mock_api.post("/urls/claim").mock(
        return_value=httpx.Response(
            200, json={"results": [{"url_id": "a" * 24, "status": "claimed"}], "claimed": 1}
        )
    )
    result = await async_client.links.claim("a" * 24, "t" * 43)
    body = json.loads(route.calls[0].request.content)
    # Wire field is `token` (NOT claim_token — the backend defines no alias)
    assert body == {"claims": [{"url_id": "a" * 24, "token": "t" * 43}]}
    assert result.status == "claimed"


@pytest.mark.asyncio
async def test_claim_many(mock_api, async_client):
    mock_api.post("/urls/claim").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"url_id": "a" * 24, "status": "claimed"},
                    {"url_id": "b" * 24, "status": "invalid"},
                ],
                "claimed": 1,
            },
        )
    )
    result = await async_client.links.claim_many([("a" * 24, "t" * 43), ("b" * 24, "u" * 43)])
    assert isinstance(result, ClaimedLinks)
    assert result.claimed == 1
    assert [r.status for r in result.results] == ["claimed", "invalid"]


@pytest.mark.asyncio
async def test_bulk_operations(mock_api, async_client):
    ids = ["a" * 24, "b" * 24]
    for op in ("delete", "status", "expiry", "domain"):
        mock_api.post(f"/urls/bulk/{op}").mock(return_value=httpx.Response(200, json=BULK_OK))

    assert isinstance(await async_client.links.bulk_delete(ids), BulkResult)
    await async_client.links.bulk_set_status(ids, "INACTIVE")
    await async_client.links.bulk_set_expiry(ids, None)
    await async_client.links.bulk_set_domain(ids, "links.acme.com")

    status_body = json.loads(mock_api.calls[1].request.content)
    assert status_body == {"ids": ids, "status": "INACTIVE"}
    expiry_body = json.loads(mock_api.calls[2].request.content)
    assert expiry_body == {"ids": ids, "expire_after": None}


@pytest.mark.asyncio
async def test_create_emoji_alias_validated_against_cached_set(mock_api, async_client):
    set_route = mock_api.get("/emoji-set").mock(return_value=httpx.Response(200, json=EMOJI_SET))
    mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN))

    await async_client.links.create("https://example.com", alias="🚀🔥")
    await async_client.links.create("https://example.com", alias="🔥")
    assert set_route.call_count == 1  # cached after the first fetch

    with pytest.raises(ValueError, match="not in the accepted emoji set"):
        await async_client.links.create("https://example.com", alias="🚀💩")
    with pytest.raises(ValueError, match="limited to 3 emoji"):
        await async_client.links.create("https://example.com", alias="🚀🔥🚀🔥")


@pytest.mark.asyncio
async def test_emoji_validation_fails_open_when_set_unavailable(mock_api, async_client):
    mock_api.get("/emoji-set").mock(return_value=httpx.Response(500, json={"error": "boom"}))
    mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN))
    url = await async_client.links.create("https://example.com", alias="🚀")
    assert url.alias == "mylink"  # server decided; client did not block


def test_emoji_canonicalization_strips_vs16_and_skin_tones():
    assert canonicalize_emoji("👍️") == "👍"
    assert canonicalize_emoji("👍🏽") == "👍"


def test_validate_emoji_alias_pure():
    accepted = frozenset({"🚀", "🔥"})
    validate_emoji_alias("🚀🔥", accepted, 3)
    with pytest.raises(ValueError):
        validate_emoji_alias("🚀x", accepted, 3)


@pytest.mark.asyncio
async def test_alias_type_passthrough(mock_api, async_client):
    route = mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN))
    await async_client.links.create("https://example.com", alias_type=AliasType.EMOJI)
    body = json.loads(route.calls[0].request.content)
    assert body["alias_type"] == "emoji"


@pytest.mark.asyncio
async def test_emoji_set_model(mock_api, async_client):
    mock_api.get("/emoji-set").mock(return_value=httpx.Response(200, json=EMOJI_SET))
    es = await async_client.links.emoji_set()
    assert isinstance(es, EmojiSet)
    assert es.max_graphemes == 3
    assert es.emoji[0].n == "rocket"
