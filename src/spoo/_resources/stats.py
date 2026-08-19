from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..types.shared import ExportFormat, GroupBy, Metric, enum_value
from ..types.stats import LinkStatsResponse, PublicStatsResponse, StatsFilter, StatsResponse
from ._base import AsyncAPIResource, SyncAPIResource

# ── Shared pure functions ────────────────────────────────────────────────


def _build_stats_params(
    *,
    start_date: str | datetime | None,
    end_date: str | datetime | None,
    group_by: list[GroupBy | str] | None,
    metrics: list[Metric | str] | None,
    timezone: str,
    filters: StatsFilter | dict[str, Any] | None,
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
        filter_dict = filters.to_dict() if isinstance(filters, StatsFilter) else filters
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
        filters: StatsFilter | dict[str, Any] | None = None,
    ) -> LinkStatsResponse:
        """Analytics for one owned link (GET /stats/links/{url_id}).

        Requires authentication. Unknown or foreign ids answer 404.
        """
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
    ) -> bytes:
        """Export account-wide analytics (GET /export). Same params as query().

        Returns the file content; write it wherever you want
        (``Path("report.csv").write_bytes(data)``).
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
        return response.content

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
        filters: StatsFilter | dict[str, Any] | None = None,
    ) -> bytes:
        """Export analytics for one owned link (GET /export/links/{url_id})."""
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
        return response.content


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
        filters: StatsFilter | dict[str, Any] | None = None,
    ) -> LinkStatsResponse:
        """Analytics for one owned link (GET /stats/links/{url_id}).

        Requires authentication. Unknown or foreign ids answer 404.
        """
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
    ) -> bytes:
        """Export account-wide analytics (GET /export). Same params as query().

        Returns the file content; write it wherever you want
        (``Path("report.csv").write_bytes(data)``).
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
        return response.content

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
        filters: StatsFilter | dict[str, Any] | None = None,
    ) -> bytes:
        """Export analytics for one owned link (GET /export/links/{url_id})."""
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
        return response.content
