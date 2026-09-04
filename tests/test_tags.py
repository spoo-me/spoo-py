"""Link tags: the tags resource, tag_ids on links, tag filters, bulk tag."""

from __future__ import annotations

import json

import httpx
import pytest

from spoo import (
    BulkResult,
    CreatedLink,
    DeletedTag,
    Link,
    LinkFilter,
    LinkStatus,
    StatsFilter,
    Tag,
    TagRef,
    UpdatedLink,
)

TAG_ID = "665f0c2f9e7a4b1d2c3d4e5f"
OTHER_TAG_ID = "665f0c2f9e7a4b1d2c3d4e60"
TAG = {
    "id": TAG_ID,
    "name": "launch",
    "color": "violet",
    "icon": "rocket",
    "link_count": 14,
    "created_at": "2026-09-01T00:00:00Z",
    "updated_at": None,
}
TAG_REF = {"id": TAG_ID, "name": "launch", "color": "violet", "icon": "rocket"}
SHORTEN = {
    "id": "a" * 24,
    "alias": "mylink",
    "short_url": "https://spoo.me/mylink",
    "long_url": "https://example.com",
    "created_at": 1704067200,
    "status": "ACTIVE",
    "tags": [TAG_REF],
}
ITEM = {"id": "a" * 24, "alias": "mylink", "password_set": False, "tags": [TAG_REF]}
UPDATED = {"id": "a" * 24, "password_set": False, "updated_at": 1704067300, "tags": []}
LIST_PAGE = {
    "items": [ITEM],
    "page": 1,
    "pageSize": 20,
    "total": 1,
    "hasNext": False,
    "sortBy": "created_at",
    "sortOrder": "descending",
}
BULK_OK = {
    "summary": {"total": 2, "succeeded": 2, "failed": 0},
    "results": [{"id": "a" * 24, "ok": True}, {"id": "b" * 24, "ok": True}],
}
STATS = {
    "filters": {},
    "group_by": ["time"],
    "timezone": "UTC",
    "time_range": {"start_date": None, "end_date": None},
    "summary": {"total_clicks": 10, "unique_clicks": 5},
    "metrics": {},
}


# ── Tags resource ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tags_list(mock_api, async_client):
    mock_api.get("/tags").mock(return_value=httpx.Response(200, json={"items": [TAG]}))
    tags = await async_client.tags.list()
    assert len(tags) == 1
    assert isinstance(tags[0], Tag)
    assert tags[0].name == "launch"
    assert tags[0].link_count == 14


@pytest.mark.asyncio
async def test_tags_create_sends_only_given_fields(mock_api, async_client):
    route = mock_api.post("/tags").mock(return_value=httpx.Response(201, json=TAG))
    tag = await async_client.tags.create("Launch")
    assert isinstance(tag, Tag)
    assert json.loads(route.calls[0].request.content) == {"name": "Launch"}

    await async_client.tags.create("launch", color="violet", icon="rocket")
    body = json.loads(route.calls[1].request.content)
    assert body == {"name": "launch", "color": "violet", "icon": "rocket"}


@pytest.mark.asyncio
async def test_tags_update_is_a_partial_patch(mock_api, async_client):
    route = mock_api.patch(f"/tags/{TAG_ID}").mock(return_value=httpx.Response(200, json=TAG))
    tag = await async_client.tags.update(TAG_ID, color="teal")
    assert tag.id == TAG_ID
    req = route.calls[0].request
    assert req.method == "PATCH"
    assert json.loads(req.content) == {"color": "teal"}


@pytest.mark.asyncio
async def test_tags_delete_reports_links_updated(mock_api, async_client):
    route = mock_api.delete(f"/tags/{TAG_ID}").mock(
        return_value=httpx.Response(200, json={"deleted": True, "links_updated": 14})
    )
    result = await async_client.tags.delete(TAG_ID)
    assert isinstance(result, DeletedTag)
    assert result.deleted is True
    assert result.links_updated == 14
    assert route.calls[0].request.method == "DELETE"


def test_sync_tags_resource(mock_api, sync_client):
    mock_api.get("/tags").mock(return_value=httpx.Response(200, json={"items": [TAG]}))
    mock_api.post("/tags").mock(return_value=httpx.Response(201, json=TAG))
    mock_api.patch(f"/tags/{TAG_ID}").mock(
        return_value=httpx.Response(200, json={**TAG, "name": "launch-2026"})
    )
    mock_api.delete(f"/tags/{TAG_ID}").mock(
        return_value=httpx.Response(200, json={"links_updated": 0})
    )

    assert sync_client.tags.list()[0].color == "violet"
    assert sync_client.tags.create("launch", icon="rocket").icon == "rocket"
    assert sync_client.tags.update(TAG_ID, name="launch-2026").name == "launch-2026"
    deleted = sync_client.tags.delete(TAG_ID)
    assert deleted.deleted is True
    assert deleted.links_updated == 0

    assert json.loads(mock_api.calls[1].request.content) == {"name": "launch", "icon": "rocket"}
    assert json.loads(mock_api.calls[2].request.content) == {"name": "launch-2026"}


def test_tag_ref_tolerates_unknown_palette_keys():
    ref = TagRef.model_validate({**TAG_REF, "color": "chartreuse", "icon": "unicorn"})
    assert ref.color == "chartreuse"


# ── tag_ids on links ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_with_tag_ids(mock_api, async_client):
    route = mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN))
    url = await async_client.links.create("https://example.com", tag_ids=[TAG_ID])
    assert isinstance(url, CreatedLink)
    assert [t.name for t in url.tags] == ["launch"]
    assert isinstance(url.tags[0], TagRef)
    assert json.loads(route.calls[0].request.content)["tag_ids"] == [TAG_ID]

    await async_client.links.create("https://example.com")
    assert "tag_ids" not in json.loads(route.calls[1].request.content)


@pytest.mark.asyncio
async def test_shorten_convenience_passes_tag_ids(mock_api, async_client):
    route = mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN))
    await async_client.shorten("https://example.com", tag_ids=[TAG_ID, OTHER_TAG_ID])
    assert json.loads(route.calls[0].request.content)["tag_ids"] == [TAG_ID, OTHER_TAG_ID]


@pytest.mark.asyncio
async def test_update_tag_ids_replaces_and_empty_clears(mock_api, async_client):
    route = mock_api.patch(f"/urls/{'a' * 24}").mock(return_value=httpx.Response(200, json=UPDATED))
    await async_client.links.update("a" * 24, tag_ids=[OTHER_TAG_ID])
    assert json.loads(route.calls[0].request.content) == {"tag_ids": [OTHER_TAG_ID]}

    result = await async_client.links.update("a" * 24, tag_ids=[])
    assert isinstance(result, UpdatedLink)
    assert result.tags == []
    assert json.loads(route.calls[1].request.content) == {"tag_ids": []}

    await async_client.links.update("a" * 24, long_url="https://example.com/new")
    assert "tag_ids" not in json.loads(route.calls[2].request.content)


@pytest.mark.asyncio
async def test_get_and_list_carry_tags(mock_api, async_client):
    mock_api.get(f"/urls/{'a' * 24}").mock(return_value=httpx.Response(200, json=ITEM))
    mock_api.get("/urls").mock(return_value=httpx.Response(200, json=LIST_PAGE))

    link = await async_client.links.get("a" * 24)
    assert isinstance(link, Link)
    assert link.tags[0].id == TAG_ID

    page = await async_client.links.list_page()
    assert page.items[0].tags[0].icon == "rocket"

    bare = Link.model_validate({"id": "b" * 24, "password_set": False})
    assert bare.tags == []


@pytest.mark.asyncio
async def test_tag_ids_rejects_a_bare_string(mock_api, async_client):
    with pytest.raises(ValueError, match="not a single string"):
        await async_client.links.create("https://example.com", tag_ids=TAG_ID)
    with pytest.raises(ValueError, match="not a single string"):
        await async_client.links.update("a" * 24, tag_ids=TAG_ID)
    assert not mock_api.calls


def test_sync_create_and_update_tag_ids(mock_api, sync_client):
    mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN))
    mock_api.patch(f"/urls/{'a' * 24}").mock(return_value=httpx.Response(200, json=UPDATED))
    url = sync_client.links.create("https://example.com", tag_ids=[TAG_ID])
    assert url.tags[0].name == "launch"
    sync_client.links.update("a" * 24, tag_ids=[])
    assert json.loads(mock_api.calls[0].request.content)["tag_ids"] == [TAG_ID]
    assert json.loads(mock_api.calls[1].request.content) == {"tag_ids": []}


# ── Link list filter ─────────────────────────────────────────────────────


def test_link_filter_tag_wire_names():
    d = LinkFilter(
        status=LinkStatus.ACTIVE,
        tag_ids=[TAG_ID],
        tag_names=["launch", "q3"],
        tags_match="all",
    ).to_dict()
    assert d == {
        "status": "ACTIVE",
        "tagIds": [TAG_ID],
        "tagNames": ["launch", "q3"],
        "tagsMatch": "all",
    }
    assert LinkFilter(search="docs").to_dict() == {"search": "docs"}


@pytest.mark.asyncio
async def test_list_page_tag_filter_in_filter_param(mock_api, async_client):
    mock_api.get("/urls").mock(return_value=httpx.Response(200, json=LIST_PAGE))
    await async_client.links.list_page(
        filter=LinkFilter(tag_names=["launch"], tags_match="any", search="docs")
    )
    req = mock_api.calls[0].request
    assert json.loads(req.url.params["filter"]) == {
        "search": "docs",
        "tagNames": ["launch"],
        "tagsMatch": "any",
    }


def test_sync_list_tag_ids_filter(mock_api, sync_client):
    mock_api.get("/urls").mock(return_value=httpx.Response(200, json=LIST_PAGE))
    items = list(sync_client.links.list(filter=LinkFilter(tag_ids=[TAG_ID, OTHER_TAG_ID])))
    assert len(items) == 1
    sent = json.loads(mock_api.calls[0].request.url.params["filter"])
    assert sent == {"tagIds": [TAG_ID, OTHER_TAG_ID]}


# ── Stats and export filters ─────────────────────────────────────────────


def test_stats_filter_tag_dimensions():
    d = StatsFilter(tag=["launch", "q3"], tag_id=[TAG_ID], country=["IN"]).to_dict()
    assert d == {"country": ["IN"], "tag": ["launch", "q3"], "tag_id": [TAG_ID]}
    assert StatsFilter(tag=[]).to_dict() == {}


@pytest.mark.asyncio
async def test_stats_query_tag_filter(mock_api, async_client):
    mock_api.get("/stats").mock(return_value=httpx.Response(200, json=STATS))
    await async_client.stats.query(filters=StatsFilter(tag=["launch"]))
    req = mock_api.calls[0].request
    assert json.loads(req.url.params["filters"]) == {"tag": ["launch"]}


@pytest.mark.asyncio
async def test_export_tag_id_filter(mock_api, async_client):
    mock_api.get("/export").mock(return_value=httpx.Response(200, content=b"csv"))
    await async_client.stats.export("csv", filters=StatsFilter(tag_id=[TAG_ID]))
    req = mock_api.calls[0].request
    assert req.url.params["format"] == "csv"
    assert json.loads(req.url.params["filters"]) == {"tag_id": [TAG_ID]}


@pytest.mark.asyncio
async def test_per_link_stats_and_export_reject_tag_filters(mock_api, async_client):
    for filters in (StatsFilter(tag=["launch"]), {"tag_id": [TAG_ID]}):
        with pytest.raises(ValueError, match="remove"):
            await async_client.stats.for_link("a" * 24, filters=filters)
        with pytest.raises(ValueError, match="remove"):
            await async_client.stats.export_link("a" * 24, "csv", filters=filters)
    assert not mock_api.calls


def test_sync_stats_and_export_tag_filters(mock_api, sync_client):
    mock_api.get("/stats").mock(return_value=httpx.Response(200, json=STATS))
    mock_api.get("/export").mock(return_value=httpx.Response(200, content=b"csv"))
    sync_client.stats.query(filters=StatsFilter(tag_id=[TAG_ID]))
    sync_client.stats.export("csv", filters=StatsFilter(tag=["launch"]))
    assert json.loads(mock_api.calls[0].request.url.params["filters"]) == {"tag_id": [TAG_ID]}
    assert json.loads(mock_api.calls[1].request.url.params["filters"]) == {"tag": ["launch"]}


# ── Bulk tag ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_update_tags_body(mock_api, async_client):
    ids = ["a" * 24, "b" * 24]
    route = mock_api.post("/urls/bulk/tags").mock(return_value=httpx.Response(200, json=BULK_OK))
    result = await async_client.links.bulk_update_tags(ids, add=[TAG_ID], remove=[OTHER_TAG_ID])
    assert isinstance(result, BulkResult)
    assert result.summary.succeeded == 2
    req = route.calls[0].request
    assert req.method == "POST"
    assert json.loads(req.content) == {"ids": ids, "add": [TAG_ID], "remove": [OTHER_TAG_ID]}

    await async_client.links.bulk_update_tags(ids, remove=[TAG_ID])
    assert json.loads(route.calls[1].request.content) == {"ids": ids, "add": [], "remove": [TAG_ID]}


@pytest.mark.asyncio
async def test_bulk_update_tags_needs_add_or_remove(mock_api, async_client):
    with pytest.raises(ValueError, match="add or remove"):
        await async_client.links.bulk_update_tags(["a" * 24])
    with pytest.raises(ValueError, match="add or remove"):
        await async_client.links.bulk_update_tags(["a" * 24], add=[], remove=[])
    assert not mock_api.calls


def test_sync_bulk_update_tags(mock_api, sync_client):
    ids = ["a" * 24, "b" * 24]
    mock_api.post("/urls/bulk/tags").mock(return_value=httpx.Response(200, json=BULK_OK))
    result = sync_client.links.bulk_update_tags(ids, add=[TAG_ID])
    assert [row.ok for row in result.results] == [True, True]
    body = json.loads(mock_api.calls[0].request.content)
    assert body == {"ids": ids, "add": [TAG_ID], "remove": []}
