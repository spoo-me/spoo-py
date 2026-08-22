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


@pytest.mark.asyncio
async def test_export_stream(mock_api, async_client):
    mock_api.get("/export").mock(
        return_value=httpx.Response(
            200,
            content=b"a" * 5000,
            headers={"Content-Disposition": 'attachment; filename="big.csv"'},
        )
    )
    chunks = []
    async with async_client.stats.export_stream("csv") as stream:
        assert stream.filename == "big.csv"
        async for chunk in stream.iter_bytes(1024):
            chunks.append(chunk)
    assert len(chunks) > 1  # actually chunked, not buffered
    assert b"".join(chunks) == b"a" * 5000


def test_sync_export_link_stream(mock_api, sync_client):
    mock_api.get("/export/links/abc").mock(
        return_value=httpx.Response(
            200,
            content=b"xlsx-bytes",
            headers={"Content-Disposition": "attachment; filename*=utf-8''..%2Fesc.xlsx"},
        )
    )
    with sync_client.stats.export_link_stream("abc", "xlsx") as stream:
        assert stream.filename == "esc.xlsx"  # sanitized on the stream path too
        data = b"".join(stream.iter_bytes())
    assert data == b"xlsx-bytes"


def test_export_stream_error_is_typed(mock_api, sync_client):
    from spoo import AuthenticationError

    mock_api.get("/export").mock(
        return_value=httpx.Response(401, json={"error": "Authentication required"})
    )
    with pytest.raises(AuthenticationError), sync_client.stats.export_stream("csv"):
        pass


@pytest.mark.asyncio
async def test_export_stream_retries_before_body(mock_api, async_client):
    route = mock_api.get("/export").mock(
        side_effect=[
            httpx.Response(500, json={"error": "boom"}),
            httpx.Response(200, content=b"ok"),
        ]
    )
    async with async_client.stats.export_stream("csv") as stream:
        data = b"".join([c async for c in stream.iter_bytes()])
    assert data == b"ok"
    assert route.call_count == 2  # GET is idempotent: pre-body retry applied
