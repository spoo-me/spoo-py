from __future__ import annotations

import httpx

from spoo import ShortenedUrl, StatsResponse

BASE_URL = "https://spoo.me/api/v1"

SHORTEN_RESPONSE = {
    "alias": "synctest",
    "short_url": "https://spoo.me/synctest",
    "long_url": "https://example.com",
    "created_at": 1704067200,
    "status": "ACTIVE",
}

STATS_RESPONSE = {
    "scope": "all",  # wire keeps the key; the SDK tolerates but does not declare it
    "filters": {},
    "group_by": ["time"],
    "timezone": "UTC",
    "time_range": {"start_date": None, "end_date": None},
    "summary": {
        "total_clicks": 10,
        "unique_clicks": 5,
        "avg_redirection_time": 100.0,
    },
    "metrics": {},
}


def test_sync_shorten(mock_api, sync_client):
    mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN_RESPONSE))
    url = sync_client.shorten("https://example.com")
    assert isinstance(url, ShortenedUrl)
    assert url.alias == "synctest"


def test_sync_urls_create(mock_api, sync_client):
    mock_api.post("/shorten").mock(return_value=httpx.Response(201, json=SHORTEN_RESPONSE))
    url = sync_client.urls.create("https://example.com", alias="synctest")
    assert url.short_url == "https://spoo.me/synctest"


def test_sync_stats_query(mock_api, sync_client):
    mock_api.get("/stats").mock(return_value=httpx.Response(200, json=STATS_RESPONSE))
    result = sync_client.stats.query()
    assert isinstance(result, StatsResponse)
    assert result.summary.total_clicks == 10
    assert "scope" not in str(mock_api.calls[0].request.url)


def test_sync_stats_for_link(mock_api, sync_client):
    mock_api.get("/stats/links/65f0c0ffee65f0c0ffee65f0").mock(
        return_value=httpx.Response(
            200, json={**STATS_RESPONSE, "url_id": "65f0c0ffee65f0c0ffee65f0", "alias": "test"}
        )
    )
    result = sync_client.stats.for_link("65f0c0ffee65f0c0ffee65f0")
    assert result.url_id == "65f0c0ffee65f0c0ffee65f0"
    assert result.alias == "test"


def test_sync_stats_public(mock_api, sync_client):
    mock_api.get("/public/stats/test").mock(
        return_value=httpx.Response(
            200,
            json={
                "generation": "v2",
                "link": {
                    "alias": "test",
                    "short_url": "https://spoo.me/test",
                    "status": "active",
                    "block_bots": False,
                    "password_protected": False,
                },
                "stats": STATS_RESPONSE,
            },
        )
    )
    result = sync_client.stats.public("test")
    assert result.generation == "v2"
    assert result.stats.summary.total_clicks == 10


def test_sync_list_page(mock_api, sync_client):
    mock_api.get("/urls").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [],
                "page": 1,
                "pageSize": 20,
                "total": 0,
                "hasNext": False,
                "sortBy": "created_at",
                "sortOrder": "descending",
            },
        )
    )
    page = sync_client.urls.list_page()
    assert page.total == 0


def test_sync_list_paginator(mock_api, sync_client):
    mock_api.get("/urls").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"id": "1", "alias": "a", "password_set": False},
                ],
                "page": 1,
                "pageSize": 20,
                "total": 1,
                "hasNext": False,
                "sortBy": "created_at",
                "sortOrder": "descending",
            },
        )
    )
    items = list(sync_client.urls.list())
    assert len(items) == 1
    assert items[0].alias == "a"
