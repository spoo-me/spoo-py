# Migrating from py_spoo_url to spoo

`spoo` 1.0 is a full rewrite of `py_spoo_url`. It targets the current spoo.me REST API (`/api/v1`), adds API key auth and an async client, and drops the bundled chart rendering. The old package keeps working against the legacy endpoints, but it no longer receives updates.

## Install

```bash
pip uninstall py_spoo_url
pip install spoo
```

Requires Python 3.10+.

## What changed

| py_spoo_url 0.0.x | spoo 1.0 |
| --- | --- |
| `from py_spoo_url import Shortener` | `from spoo import SpooClient` |
| `Shortener().shorten(url, alias=..., password=..., max_clicks=...)` returns a string | `client.shorten(url, alias=..., password=..., max_clicks=...)` returns a `CreatedLink` model (`.short_url` for the string) |
| `Shortener().emoji(url, emoji_alias=...)` | `client.shorten(url, alias="🚀🔥")` for a chosen alias, or `client.shorten(url, alias_type="emoji")` to auto-generate one. The SDK validates emoji against the server's accepted catalogue before sending. |
| `Statistics(short_code, password=...)` fetches stats on init | `client.stats.public(short_code, password=...)` for public links, `client.stats.for_link(url_id)` for links you own, `client.stats.query(...)` across your account |
| `Statistics.export_data(format=...)` writes a file | `client.stats.export(format)` returns bytes; write them with `Path(...).write_bytes(data)` |
| `Statistics.make_chart(...)`, `make_countries_heatmap(...)` | Removed. The SDK returns data; plot it with whatever you already use. This is what dropped the install from hundreds of MB (matplotlib, geopandas, pandas) to two small dependencies. |
| No auth | `SpooClient(api_key="spoo_...")` or the `SPOO_API_KEY` environment variable |
| Sync only, `requests` | Sync `SpooClient` and async `AsyncSpooClient`, both on `httpx` |
| Raises `requests` exceptions with raw status codes | Typed exceptions: `ValidationError`, `NotFoundError`, `RateLimitError`, and friends, each carrying the backend `error_code` |

## Quick before and after

Shortening:

```python
# before
from py_spoo_url import Shortener
short_url = Shortener().shorten("https://example.com", alias="mylink")

# after
from spoo import SpooClient
client = SpooClient()
short_url = client.shorten("https://example.com", alias="mylink").short_url
```

Stats and export:

```python
# before
from py_spoo_url import Statistics
stats = Statistics("mylink")
print(stats.total_clicks)
stats.export_data("xlsx", "report.xlsx")

# after
from pathlib import Path
from spoo import SpooClient, ExportFormat
client = SpooClient(api_key="spoo_...")
stats = client.stats.public("mylink")
print(stats.stats.summary.total_clicks)
Path("report.xlsx").write_bytes(client.stats.export(ExportFormat.XLSX))
```

## New things worth knowing

- Everything you own is manageable: `client.links.list()`, `.update()`, `.set_status()`, `.delete()`.
- `client.links.check_alias("name")` tells you whether an alias is free before you create.
- Account-wide analytics with grouping and filters: `client.stats.query(group_by=[...], filters=...)`.
- Custom domains: pass `domain="links.acme.com"` to create, list, and shorten calls.
- Automatic retries on 429 and 5xx with `Retry-After` support.

See the [README](README.md) for the full tour.
