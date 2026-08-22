from __future__ import annotations

import contextlib
import json
import re
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Any
from urllib.parse import unquote

import httpx

from ..types.shared import ExportFormat, GroupBy, Metric, enum_value
from ..types.stats import (
    ExportFile,
    LinkStatsFilter,
    LinkStatsResponse,
    PublicStatsResponse,
    StatsFilter,
    StatsResponse,
)
from ._base import AsyncAPIResource, SyncAPIResource

# RFC 5987 form first (filename*=utf-8''...), plain filename= as fallback.
_FILENAME_STAR_RE = re.compile(r"filename\*=utf-8''([^;]+)", re.IGNORECASE)
_FILENAME_RE = re.compile(r'filename="?([^";]+)"?', re.IGNORECASE)


def _sanitize_filename(name: str | None) -> str | None:
    """Reduce a wire-supplied filename to a bare, safe basename.

    The header comes from whatever the base URL points at, and consumers use
    the result as a path. Traversal, absolute paths, and separator smuggling
    must die here, in the SDK, not in every consumer.
    """
    if not name:
        return None
    # Take the last segment across both separator conventions.
    for sep in ("/", "\\"):
        name = name.rsplit(sep, 1)[-1]
    name = name.strip()
    if name in ("", ".", "..") or name.startswith("~"):
        return None
    return name


def _filename_from_headers(headers: httpx.Headers) -> str | None:
    disposition = headers.get("Content-Disposition", "")
    match = _FILENAME_STAR_RE.search(disposition)
    filename = unquote(match.group(1)) if match else None
    if filename is None:
        plain = _FILENAME_RE.search(disposition)
        filename = plain.group(1) if plain else None
    return _sanitize_filename(filename)


def _export_file(response: httpx.Response) -> ExportFile:
    return ExportFile(
        response.content,
        filename=_filename_from_headers(response.headers),
        content_type=response.headers.get("Content-Type"),
    )


class ExportStream:
    """A streaming export: iterate chunks instead of buffering the file.

    Carries the same sanitized ``filename`` and ``content_type`` as
    :class:`ExportFile`. Only valid inside its ``with`` block.
    """

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.filename = _filename_from_headers(response.headers)
        self.content_type: str | None = response.headers.get("Content-Type")

    def iter_bytes(self, chunk_size: int | None = None) -> Iterator[bytes]:
        return self._response.iter_bytes(chunk_size)


class AsyncExportStream:
    """Async twin of :class:`ExportStream` (``async for`` over iter_bytes)."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.filename = _filename_from_headers(response.headers)
        self.content_type: str | None = response.headers.get("Content-Type")

    def iter_bytes(self, chunk_size: int | None = None) -> AsyncIterator[bytes]:
        return self._response.aiter_bytes(chunk_size)


def _reject_identity_filters(filters: LinkStatsFilter | dict[str, Any] | None) -> None:
    if filters is None:
        return
    d = filters.to_dict() if isinstance(filters, LinkStatsFilter) else filters
    bad = {"short_code", "url_id"} & set(d)
    if bad:
        raise ValueError(
            f"per-link endpoints already carry the link identity; remove {sorted(bad)} from filters"
        )


# ── Shared pure functions ────────────────────────────────────────────────


def _build_stats_params(
    *,
    start_date: str | datetime | None,
    end_date: str | datetime | None,
    group_by: list[GroupBy | str] | None,
    metrics: list[Metric | str] | None,
    timezone: str,
    filters: LinkStatsFilter | dict[str, Any] | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "timezone": timezone,
    }
    if start_date is not None:
        params["start_date"] = _serialize_dt(start_date)
    if end_date is not None:
        params["end_date"] = _serialize_dt(end_date)
    if group_by is not None:
        params["group_by"] = ",".join(enum_value(g) for g in group_by)
    if metrics is not None:
        params["metrics"] = ",".join(enum_value(m) for m in metrics)
    if filters is not None:
        filter_dict = filters.to_dict() if isinstance(filters, LinkStatsFilter) else filters
        if filter_dict:
            params["filters"] = json.dumps(filter_dict)
    return params


def _build_public_stats_params(
    *,
    start_date: str | datetime | None,
    end_date: str | datetime | None,
    timezone: str,
) -> dict[str, Any]:
    params: dict[str, Any] = {"timezone": timezone}
    if start_date is not None:
        params["start_date"] = _serialize_dt(start_date)
    if end_date is not None:
        params["end_date"] = _serialize_dt(end_date)
    return params


def _serialize_dt(value: str | datetime) -> str:
    return value.isoformat() if isinstance(value, datetime) else value


# ── Async resource ───────────────────────────────────────────────────────


class AsyncStats(AsyncAPIResource):
    """Click analytics queries (async)."""

    async def query(
        self,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: StatsFilter | dict[str, Any] | None = None,
    ) -> StatsResponse:
        """Account-wide analytics (GET /stats). Requires authentication.

        To slice by link, pass ``short_code`` or ``url_id`` in ``filters``;
        for a single link, prefer :meth:`for_link`.
        """
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        return await self._transport.request("GET", "/stats", params=params, cast_to=StatsResponse)

    async def for_link(
        self,
        url_id: str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: LinkStatsFilter | dict[str, Any] | None = None,
    ) -> LinkStatsResponse:
        """Analytics for one owned link (GET /stats/links/{url_id}).

        Requires authentication. Unknown or foreign ids answer 404.
        """
        _reject_identity_filters(filters)
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        return await self._transport.request(
            "GET", f"/stats/links/{url_id}", params=params, cast_to=LinkStatsResponse
        )

    async def public(
        self,
        short_code: str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        timezone: str = "UTC",
        password: str | None = None,
    ) -> PublicStatsResponse:
        """Public stats for a single link (GET|POST /public/stats/{short_code}).

        No authentication required. Password-protected links answer 401
        ``password_required``; pass ``password`` to unlock (it travels in a
        POST body, never in the URL).
        """
        params = _build_public_stats_params(
            start_date=start_date, end_date=end_date, timezone=timezone
        )
        path = f"/public/stats/{short_code}"
        if password is None:
            return await self._transport.request(
                "GET", path, params=params, cast_to=PublicStatsResponse
            )
        return await self._transport.request(
            "POST", path, params=params, json={"password": password}, cast_to=PublicStatsResponse
        )

    async def export(
        self,
        format: ExportFormat | str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: StatsFilter | dict[str, Any] | None = None,
    ) -> ExportFile:
        """Export account-wide analytics (GET /export). Same params as query().

        Returns the file content as bytes, with the server's suggested
        ``filename`` and ``content_type`` attached
        (``Path(data.filename or "export.csv").write_bytes(data)``).
        """
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        params["format"] = enum_value(format)
        response = await self._transport.request_raw("GET", "/export", params=params)
        return _export_file(response)

    async def export_link(
        self,
        url_id: str,
        format: ExportFormat | str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: LinkStatsFilter | dict[str, Any] | None = None,
    ) -> ExportFile:
        """Export analytics for one owned link (GET /export/links/{url_id}).

        The returned file carries the link's own filename from the server.
        """
        _reject_identity_filters(filters)
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        params["format"] = enum_value(format)
        response = await self._transport.request_raw(
            "GET", f"/export/links/{url_id}", params=params
        )
        return _export_file(response)

    @contextlib.asynccontextmanager
    async def export_stream(
        self,
        format: ExportFormat | str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: StatsFilter | dict[str, Any] | None = None,
    ) -> AsyncIterator[AsyncExportStream]:
        """Stream an account-wide export instead of buffering it in memory.

        Usage::

            async with client.stats.export_stream("xlsx") as stream:
                with open(stream.filename or "export.xlsx", "wb") as f:
                    async for chunk in stream.iter_bytes():
                        f.write(chunk)
        """
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        params["format"] = enum_value(format)
        async with self._transport.stream("GET", "/export", params=params) as response:
            yield AsyncExportStream(response)

    @contextlib.asynccontextmanager
    async def export_link_stream(
        self,
        url_id: str,
        format: ExportFormat | str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: LinkStatsFilter | dict[str, Any] | None = None,
    ) -> AsyncIterator[AsyncExportStream]:
        """Stream one owned link's export instead of buffering it."""
        _reject_identity_filters(filters)
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        params["format"] = enum_value(format)
        async with self._transport.stream(
            "GET", f"/export/links/{url_id}", params=params
        ) as response:
            yield AsyncExportStream(response)


# ── Sync resource ────────────────────────────────────────────────────────


class Stats(SyncAPIResource):
    """Click analytics queries (sync)."""

    def query(
        self,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: StatsFilter | dict[str, Any] | None = None,
    ) -> StatsResponse:
        """Account-wide analytics (GET /stats). Requires authentication.

        To slice by link, pass ``short_code`` or ``url_id`` in ``filters``;
        for a single link, prefer :meth:`for_link`.
        """
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        return self._transport.request("GET", "/stats", params=params, cast_to=StatsResponse)

    def for_link(
        self,
        url_id: str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: LinkStatsFilter | dict[str, Any] | None = None,
    ) -> LinkStatsResponse:
        """Analytics for one owned link (GET /stats/links/{url_id}).

        Requires authentication. Unknown or foreign ids answer 404.
        """
        _reject_identity_filters(filters)
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        return self._transport.request(
            "GET", f"/stats/links/{url_id}", params=params, cast_to=LinkStatsResponse
        )

    def public(
        self,
        short_code: str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        timezone: str = "UTC",
        password: str | None = None,
    ) -> PublicStatsResponse:
        """Public stats for a single link (GET|POST /public/stats/{short_code}).

        No authentication required. Password-protected links answer 401
        ``password_required``; pass ``password`` to unlock (it travels in a
        POST body, never in the URL).
        """
        params = _build_public_stats_params(
            start_date=start_date, end_date=end_date, timezone=timezone
        )
        path = f"/public/stats/{short_code}"
        if password is None:
            return self._transport.request("GET", path, params=params, cast_to=PublicStatsResponse)
        return self._transport.request(
            "POST", path, params=params, json={"password": password}, cast_to=PublicStatsResponse
        )

    def export(
        self,
        format: ExportFormat | str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: StatsFilter | dict[str, Any] | None = None,
    ) -> ExportFile:
        """Export account-wide analytics (GET /export). Same params as query().

        Returns the file content as bytes, with the server's suggested
        ``filename`` and ``content_type`` attached
        (``Path(data.filename or "export.csv").write_bytes(data)``).
        """
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        params["format"] = enum_value(format)
        response = self._transport.request_raw("GET", "/export", params=params)
        return _export_file(response)

    def export_link(
        self,
        url_id: str,
        format: ExportFormat | str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: LinkStatsFilter | dict[str, Any] | None = None,
    ) -> ExportFile:
        """Export analytics for one owned link (GET /export/links/{url_id}).

        The returned file carries the link's own filename from the server.
        """
        _reject_identity_filters(filters)
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        params["format"] = enum_value(format)
        response = self._transport.request_raw("GET", f"/export/links/{url_id}", params=params)
        return _export_file(response)

    @contextlib.contextmanager
    def export_stream(
        self,
        format: ExportFormat | str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: StatsFilter | dict[str, Any] | None = None,
    ) -> Iterator[ExportStream]:
        """Stream an account-wide export instead of buffering it in memory.

        Usage::

            with client.stats.export_stream("xlsx") as stream:
                with open(stream.filename or "export.xlsx", "wb") as f:
                    for chunk in stream.iter_bytes():
                        f.write(chunk)
        """
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        params["format"] = enum_value(format)
        with self._transport.stream("GET", "/export", params=params) as response:
            yield ExportStream(response)

    @contextlib.contextmanager
    def export_link_stream(
        self,
        url_id: str,
        format: ExportFormat | str,
        *,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        group_by: list[GroupBy | str] | None = None,
        metrics: list[Metric | str] | None = None,
        timezone: str = "UTC",
        filters: LinkStatsFilter | dict[str, Any] | None = None,
    ) -> Iterator[ExportStream]:
        """Stream one owned link's export instead of buffering it."""
        _reject_identity_filters(filters)
        params = _build_stats_params(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            metrics=metrics,
            timezone=timezone,
            filters=filters,
        )
        params["format"] = enum_value(format)
        with self._transport.stream("GET", f"/export/links/{url_id}", params=params) as response:
            yield ExportStream(response)
