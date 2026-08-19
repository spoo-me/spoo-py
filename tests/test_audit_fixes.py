"""Regression tests for the 2026-08 cross-SDK audit findings."""

from __future__ import annotations

import httpx
import pytest

from spoo import (
    ContentBlockedError,
    ExportFile,
    LinkStatsFilter,
    PayloadTooLargeError,
    PublicPreview,
    RateLimitError,
    ServiceUnavailableError,
    SpooClient,
    StatsFilter,
)
from spoo._errors import parse_retry_after

LINK_STATS = {
    "scope": "link",
    "filters": {},
    "group_by": ["time"],
    "timezone": "UTC",
    "time_range": {"start_date": None, "end_date": None},
    "summary": {
        "total_clicks": 1,
        "unique_clicks": 1,
        "first_click": None,
        "last_click": None,
        "avg_redirection_time": None,
    },
}


def test_parse_retry_after_forms():
    assert parse_retry_after("120") == 120.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("Wed, 21 Oct 2093 07:28:00 GMT") > 0  # future date
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0  # past clamps
    assert parse_retry_after("garbage") is None


def test_http_date_retry_after_does_not_crash(mock_api):
    client = SpooClient(api_key="spoo_test", base_url="https://spoo.me/api/v1", max_retries=0)
    mock_api.get("/urls/abc").mock(
        return_value=httpx.Response(
            429,
            json={"error": "limited", "code": "rate_limit_exceeded"},
            headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"},
        )
    )
    with pytest.raises(RateLimitError) as exc_info:  # not ValueError
        client.urls.get("abc")
    assert exc_info.value.retry_after == 0.0


def test_edge_composed_error_uses_header_code_and_clean_message(mock_api):
    client = SpooClient(api_key="spoo_test", base_url="https://spoo.me/api/v1", max_retries=0)
    mock_api.get("/urls/abc").mock(
        return_value=httpx.Response(
            451,
            content=b"<!DOCTYPE html><html>blocked page</html>",
            headers={"X-Error-Code": "blocked", "Content-Type": "text/html"},
        )
    )
    with pytest.raises(ContentBlockedError) as exc_info:
        client.urls.get("abc")
    err = exc_info.value
    assert err.error_code == "blocked"
    assert err.message == "HTTP 451"  # never the raw HTML
    assert err.body is not None and "blocked page" in err.body["raw"]


def test_new_status_classes(mock_api):
    client = SpooClient(api_key="spoo_test", base_url="https://spoo.me/api/v1", max_retries=0)
    mock_api.get("/urls/a").mock(return_value=httpx.Response(413, json={"error": "too big"}))
    with pytest.raises(PayloadTooLargeError):
        client.urls.get("a")
    mock_api.get("/urls/b").mock(return_value=httpx.Response(503, json={"error": "down"}))
    with pytest.raises(ServiceUnavailableError):
        client.urls.get("b")


@pytest.mark.asyncio
async def test_export_carries_filename(mock_api, async_client):
    mock_api.get("/export/links/abc").mock(
        return_value=httpx.Response(
            200,
            content=b"csv-data",
            headers={
                "Content-Disposition": "attachment; filename*=utf-8''mylink%20stats.csv",
                "Content-Type": "text/csv",
            },
        )
    )
    data = await async_client.stats.export_link("abc", "csv")
    assert isinstance(data, ExportFile)
    assert bytes(data) == b"csv-data"
    assert data.filename == "mylink stats.csv"
    assert data.content_type == "text/csv"

    mock_api.get("/export").mock(
        return_value=httpx.Response(
            200,
            content=b"agg",
            headers={"Content-Disposition": 'attachment; filename="spoo-me-export.csv"'},
        )
    )
    agg = await async_client.stats.export("csv")
    assert agg.filename == "spoo-me-export.csv"


@pytest.mark.asyncio
async def test_for_link_rejects_identity_filters(mock_api, async_client):
    with pytest.raises(ValueError, match="link identity"):
        await async_client.stats.for_link("abc", filters={"url_id": ["abc"]})
    with pytest.raises(ValueError, match="link identity"):
        await async_client.stats.for_link("abc", filters=StatsFilter(short_code=["x"]))
    # clean per-link filters pass through
    mock_api.get("/stats/links/abc").mock(return_value=httpx.Response(200, json=LINK_STATS))
    await async_client.stats.for_link("abc", filters=LinkStatsFilter(country=["IN"]))


@pytest.mark.asyncio
async def test_public_preview(mock_api, async_client):
    mock_api.get("/public/preview/mylink").mock(
        return_value=httpx.Response(
            200,
            json={
                "generation": "v2",
                "alias": "mylink",
                "short_url": "https://spoo.me/mylink",
                "status": "active",
                "password_protected": False,
                "destination": {
                    "url": "https://example.com/page",
                    "domain": "example.com",
                    "path": "/page",
                    "is_https": True,
                },
            },
        )
    )
    preview = await async_client.urls.preview("mylink")
    assert isinstance(preview, PublicPreview)
    assert preview.destination is not None
    assert preview.destination.domain == "example.com"
    assert preview.password_protected is False
