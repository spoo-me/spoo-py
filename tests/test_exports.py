"""stats.export / stats.export_link — analytics as files."""

from __future__ import annotations

import httpx
import pytest

from spoo import ExportFormat


@pytest.mark.asyncio
async def test_export_bytes(mock_api, async_client):
    mock_api.get("/export").mock(return_value=httpx.Response(200, content=b'{"data": "export"}'))
    data = await async_client.stats.export(ExportFormat.JSON)
    assert isinstance(data, bytes)
    assert b"export" in data

    req = mock_api.calls[0].request
    assert "format=json" in str(req.url)
    assert "scope" not in str(req.url)


@pytest.mark.asyncio
async def test_export_shares_stats_params(mock_api, async_client):
    from spoo import GroupBy, StatsFilter

    mock_api.get("/export").mock(return_value=httpx.Response(200, content=b"csv"))
    window = dict(
        start_date="2026-07-01",
        group_by=[GroupBy.TIME, GroupBy.DEVICE],
        filters=StatsFilter(country=["IN"]),
        timezone="Asia/Kolkata",
    )
    await async_client.stats.export(ExportFormat.CSV, **window)
    url = str(mock_api.calls[0].request.url)
    assert "start_date=2026-07-01" in url
    assert "group_by=time%2Cdevice" in url
    assert "timezone=Asia%2FKolkata" in url


@pytest.mark.asyncio
async def test_export_link(mock_api, async_client):
    url_id = "a" * 24
    mock_api.get(f"/export/links/{url_id}").mock(
        return_value=httpx.Response(200, content=b"xlsx-binary-data")
    )
    data = await async_client.stats.export_link(url_id, "xlsx")
    assert data == b"xlsx-binary-data"


def test_sync_export(mock_api, sync_client):
    mock_api.get("/export").mock(return_value=httpx.Response(200, content=b"csv-data"))
    assert sync_client.stats.export("csv") == b"csv-data"
