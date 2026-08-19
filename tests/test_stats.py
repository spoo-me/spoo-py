from __future__ import annotations

import httpx
import pytest

from spoo import (
    LinkStatsResponse,
    NotFoundError,
    PublicStatsResponse,
    StatsResponse,
)

BASE_URL = "https://spoo.me/api/v1"

STATS_RESPONSE = {
    # The wire keeps a "scope" key for now — the SDK tolerates but does not
    # declare it (it is not part of the public API).
    "scope": "all",
    "filters": {},
    "group_by": ["time"],
    "timezone": "UTC",
    "time_range": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
    "summary": {
        "total_clicks": 1000,
        "unique_clicks": 250,
        "first_click": "2024-01-01T10:00:00Z",
        "last_click": "2024-12-31T23:59:00Z",
        "avg_redirection_time": 125.5,
    },
    "metrics": {"clicks_by_time": [{"time": "2024-01-01", "clicks": 50, "clicks_percentage": 5.0}]},
    "computed_metrics": {
        "unique_click_rate": 0.25,
        "repeat_click_rate": 0.75,
        "average_clicks_per_visitor": 4.0,
    },
}

LINK_STATS_RESPONSE = {
    **STATS_RESPONSE,
    "url_id": "65f0c0ffee65f0c0ffee65f0",
    "alias": "mylink",
}

PUBLIC_STATS_RESPONSE = {
    "generation": "v2",
    "link": {
        "alias": "mylink",
        "short_url": "https://spoo.me/mylink",
        "long_url": "https://example.com",
        "created_at": "2024-01-01T00:00:00Z",
        "status": "active",
        "max_clicks": None,
        "block_bots": False,
        "password_protected": False,
    },
    "stats": STATS_RESPONSE,
}


@pytest.mark.asyncio
async def test_stats_query(mock_api, async_client):
    mock_api.get("/stats").mock(return_value=httpx.Response(200, json=STATS_RESPONSE))
    result = await async_client.stats.query()
    assert isinstance(result, StatsResponse)
    assert result.summary.total_clicks == 1000
    assert result.summary.unique_clicks == 250
    assert "clicks_by_time" in result.metrics

    # scope is gone from the request surface entirely
    req = mock_api.calls[0].request
    assert "scope" not in str(req.url)


@pytest.mark.asyncio
async def test_stats_for_link(mock_api, async_client):
    mock_api.get("/stats/links/65f0c0ffee65f0c0ffee65f0").mock(
        return_value=httpx.Response(200, json=LINK_STATS_RESPONSE)
    )
    result = await async_client.stats.for_link("65f0c0ffee65f0c0ffee65f0")
    assert isinstance(result, LinkStatsResponse)
    assert result.url_id == "65f0c0ffee65f0c0ffee65f0"
    assert result.alias == "mylink"
    assert result.computed_metrics is not None
    assert result.computed_metrics.unique_click_rate == 0.25


@pytest.mark.asyncio
async def test_stats_for_link_not_found(mock_api, async_client):
    mock_api.get("/stats/links/000000000000000000000000").mock(
        return_value=httpx.Response(404, json={"error": "URL not found", "code": "not_found"})
    )
    with pytest.raises(NotFoundError):
        await async_client.stats.for_link("000000000000000000000000")


@pytest.mark.asyncio
async def test_stats_with_filters(mock_api, async_client):
    mock_api.get("/stats").mock(return_value=httpx.Response(200, json=STATS_RESPONSE))
    from spoo import GroupBy, Metric, StatsFilter

    result = await async_client.stats.query(
        group_by=[GroupBy.TIME, GroupBy.BROWSER],
        metrics=[Metric.CLICKS],
        filters=StatsFilter(browser=["Chrome", "Firefox"]),
        timezone="America/New_York",
    )
    assert result.summary.total_clicks == 1000

    req = mock_api.calls[0].request
    assert "group_by=time%2Cbrowser" in str(req.url) or "group_by=time,browser" in str(req.url)


@pytest.mark.asyncio
async def test_stats_url_id_filter(mock_api, async_client):
    mock_api.get("/stats").mock(return_value=httpx.Response(200, json=STATS_RESPONSE))
    from spoo import StatsFilter

    await async_client.stats.query(
        filters=StatsFilter(url_id=["65f0c0ffee65f0c0ffee65f0"], short_code=["mylink"])
    )

    req = mock_api.calls[0].request
    assert "url_id" in str(req.url)
    assert "short_code" in str(req.url)


@pytest.mark.asyncio
async def test_stats_public(mock_api, async_client):
    mock_api.get("/public/stats/mylink").mock(
        return_value=httpx.Response(200, json=PUBLIC_STATS_RESPONSE)
    )
    result = await async_client.stats.public("mylink")
    assert isinstance(result, PublicStatsResponse)
    assert result.generation == "v2"
    assert result.link.alias == "mylink"
    assert result.link.password_protected is False
    assert result.stats.summary.total_clicks == 1000


@pytest.mark.asyncio
async def test_stats_public_with_password(mock_api, async_client):
    mock_api.post("/public/stats/mylink").mock(
        return_value=httpx.Response(200, json=PUBLIC_STATS_RESPONSE)
    )
    result = await async_client.stats.public("mylink", password="Secret.12")
    assert result.stats.summary.unique_clicks == 250

    req = mock_api.calls[0].request
    assert req.method == "POST"
    assert b'"password"' in req.content
    # The password never travels in the URL
    assert "Secret.12" not in str(req.url)
