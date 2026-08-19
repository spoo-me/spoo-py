from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StatsSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    total_clicks: int
    unique_clicks: int
    first_click: str | None = None
    last_click: str | None = None
    avg_redirection_time: float | None = None


class StatsTimeRange(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    start_date: str | None = None
    end_date: str | None = None


class ComputedMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    unique_click_rate: float
    repeat_click_rate: float
    average_clicks_per_visitor: float


class TimeBucketInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    strategy: str
    mongo_format: str
    display_format: str
    timezone: str
    interval_minutes: int | None = None


class StatsResponse(BaseModel):
    """Response from GET /api/v1/stats (account-wide analytics)."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    filters: dict[str, Any]
    group_by: list[str]
    timezone: str
    time_range: StatsTimeRange
    summary: StatsSummary
    metrics: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    generated_at: str | None = None
    api_version: str | None = None
    time_bucket_info: TimeBucketInfo | None = None
    computed_metrics: ComputedMetrics | None = None


class LinkStatsResponse(StatsResponse):
    """Response from GET /api/v1/stats/links/{url_id} (one owned link).

    Same stats wire as :class:`StatsResponse`, plus the resolved link echoed
    at the top level.
    """

    url_id: str | None = None
    alias: str | None = None


class PublicLinkFacts(BaseModel):
    """Public facts about a link, shown alongside its public stats."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    alias: str
    short_url: str
    long_url: str | None = None
    created_at: str | None = None
    status: str
    max_clicks: int | None = None
    block_bots: bool
    password_protected: bool


class PublicStatsResponse(BaseModel):
    """Response from GET|POST /api/v1/public/stats/{short_code}.

    ``stats`` carries the same wire shape as :class:`StatsResponse`.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    generation: str
    link: PublicLinkFacts
    stats: StatsResponse


class LinkStatsFilter:
    """Dimension filters valid on per-link stats and exports.

    Deliberately excludes ``short_code`` and ``url_id``: the per-link
    endpoints carry the link identity in the path and reject those filters.
    Use :class:`StatsFilter` for account-wide queries.
    """

    _FIELDS: tuple[str, ...] = (
        "browser",
        "os",
        "device",
        "country",
        "city",
        "referrer",
        "utm_source",
        "utm_medium",
        "utm_campaign",
    )

    def __init__(
        self,
        *,
        browser: list[str] | None = None,
        os: list[str] | None = None,
        device: list[str] | None = None,
        country: list[str] | None = None,
        city: list[str] | None = None,
        referrer: list[str] | None = None,
        utm_source: list[str] | None = None,
        utm_medium: list[str] | None = None,
        utm_campaign: list[str] | None = None,
    ) -> None:
        self.browser = browser
        self.os = os
        self.device = device
        self.country = country
        self.city = city
        self.referrer = referrer
        self.utm_source = utm_source
        self.utm_medium = utm_medium
        self.utm_campaign = utm_campaign

    def to_dict(self) -> dict[str, list[str]]:
        d: dict[str, list[str]] = {}
        for name in self._FIELDS:
            value = getattr(self, name)
            if value:
                d[name] = value
        return d


class StatsFilter(LinkStatsFilter):
    """Filter object for account-wide stats queries. Serialized to JSON."""

    _FIELDS = (*LinkStatsFilter._FIELDS, "short_code", "url_id")

    def __init__(
        self,
        *,
        short_code: list[str] | None = None,
        url_id: list[str] | None = None,
        **dimensions: list[str] | None,
    ) -> None:
        super().__init__(**dimensions)
        self.short_code = short_code
        self.url_id = url_id


class ExportFile(bytes):
    """Export content that still behaves as ``bytes``, plus the server's
    suggested ``filename`` and ``content_type`` from the response headers.

    ``Path(export.filename or "export.csv").write_bytes(export)`` works
    unchanged; the filename is what makes per-link exports distinguishable.
    """

    filename: str | None
    content_type: str | None

    def __new__(
        cls, content: bytes, *, filename: str | None = None, content_type: str | None = None
    ) -> ExportFile:
        obj = super().__new__(cls, content)
        obj.filename = filename
        obj.content_type = content_type
        return obj
