from __future__ import annotations

from enum import Enum


def enum_value(v: Enum | str) -> str:
    """Extract the string value from an enum or pass through a string."""
    return v.value if isinstance(v, Enum) else str(v)


class LinkStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class SortBy(str, Enum):
    CREATED_AT = "created_at"
    LAST_CLICK = "last_click"
    TOTAL_CLICKS = "total_clicks"


class SortOrder(str, Enum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    XML = "xml"


class GroupBy(str, Enum):
    TIME = "time"
    BROWSER = "browser"
    OS = "os"
    DEVICE = "device"
    COUNTRY = "country"
    CITY = "city"
    REFERRER = "referrer"
    SHORT_CODE = "short_code"
    UTM_SOURCE = "utm_source"
    UTM_MEDIUM = "utm_medium"
    UTM_CAMPAIGN = "utm_campaign"


class AliasType(str, Enum):
    ALPHANUMERIC = "alphanumeric"
    EMOJI = "emoji"


class Metric(str, Enum):
    CLICKS = "clicks"
    UNIQUE_CLICKS = "unique_clicks"
