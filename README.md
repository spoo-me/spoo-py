# spoo

The official Python SDK for the [spoo.me](https://spoo.me) URL shortener API.

[![CI](https://img.shields.io/github/actions/workflow/status/spoo-me/spoo-py/ci.yml?branch=main&label=CI)](https://github.com/spoo-me/spoo-py/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/spoo)](https://pypi.org/project/spoo/)
[![Python](https://img.shields.io/pypi/pyversions/spoo)](https://pypi.org/project/spoo/)
[![Codecov](https://img.shields.io/codecov/c/github/spoo-me/spoo-py)](https://codecov.io/gh/spoo-me/spoo-py)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

```python
from spoo import SpooClient

client = SpooClient()
print(client.shorten("https://example.com").short_url)
```

- Sync and async clients with the same API
- Fully typed: every response is a Pydantic model, `py.typed` included
- Sign in with Spoo (PKCE device auth) with automatic token refresh
- Automatic, idempotency-aware retries
- Auto-pagination for list endpoints
- Two runtime dependencies: `httpx` and `pydantic`

Migrating from `py_spoo_url`? See [MIGRATION.md](MIGRATION.md).

## Install

```bash
pip install spoo
# or
uv add spoo
```

Requires Python 3.10+.

## Authentication

```python
client = SpooClient()                    # reads SPOO_API_KEY, else anonymous
client = SpooClient(api_key="spoo_...")  # explicit API key
client = SpooClient(api_key="")          # force anonymous even with env set
client = SpooClient(bearer_token=...)    # a JWT, or a callable returning one
```

Anonymous clients work under anonymous limits. Create API keys from your spoo.me dashboard. Self-hosting? Point `base_url` (or `SPOO_BASE_URL`) at your instance's `/api/v1`.

Note that the base URL is a security boundary: every request, credential, and server-suggested filename flows through whatever it points at. Prefer the explicit `base_url` argument in anything security-sensitive, since the environment variable can redirect a whole process without any call site showing it.

Async is the same surface with `AsyncSpooClient`, `await`, and `async for`.

## Links

```python
from spoo import SpooClient, UrlFilter, UrlStatus, SortBy

client = SpooClient(api_key="spoo_...")

url = client.urls.create(
    "https://example.com",
    alias="mylink",
    password="Secret@123",
    max_clicks=500,
    expire_after="2026-12-31T00:00:00",
    block_bots=True,
    private_stats=True,
)

# Check availability first if you want a precise reason
check = client.urls.check_alias("mylink")
if not check.available:
    print(check.reason)  # taken | format | length | reserved | emoji_policy

# Fetch one link by id, or by its address
link = client.urls.get(url.id)
preview = client.urls.preview("mylink")   # public: destination, status, protection
link = client.urls.get_by_alias("mylink")                    # your base domain
link = client.urls.get_by_alias("mylink", domain="links.acme.com")

# Iterate everything (auto-pagination), or one filtered page
for item in client.urls.list(sort_by=SortBy.TOTAL_CLICKS):
    print(item.alias, item.total_clicks)
page = client.urls.list_page(filter=UrlFilter(status=UrlStatus.ACTIVE, search="docs"))

# Update, toggle, delete
client.urls.update(url.id, long_url="https://example.com/new", max_clicks=0)
client.urls.set_status(url.id, UrlStatus.INACTIVE)
client.urls.delete(url.id)
```

### Bulk operations

Up to 100 ids per call; results are reported per item instead of throwing:

```python
result = client.urls.bulk_set_status(ids, UrlStatus.INACTIVE)
print(result.summary.succeeded, result.summary.failed)
for row in result.results:
    if not row.ok:
        print(row.id, row.error_code)

client.urls.bulk_delete(ids)
client.urls.bulk_set_expiry(ids, "2027-01-01T00:00:00")   # None clears
client.urls.bulk_set_domain(ids, "links.acme.com")        # None = default
```

### Emoji aliases

```python
url = client.shorten("https://example.com", alias="🚀🔥")       # pick your own
url = client.shorten("https://example.com", alias_type="emoji")  # auto-generate
```

The SDK validates emoji aliases before sending, against the server's own accepted catalogue (fetched once per client and cached). The catalogue is available directly for building pickers:

```python
emoji_set = client.urls.emoji_set()   # ~1170 entries with names and groups
```

### Claim links

Anonymous creates return a one-time `claim_token`. After the user signs in, the token proves they created the link and transfers ownership, stats included:

```python
anon_url = SpooClient(api_key="").shorten("https://example.com")

result = client.urls.claim(anon_url.id, anon_url.claim_token)
print(result.status)   # claimed | already_yours | invalid

client.urls.claim_many([(id1, token1), (id2, token2)])   # up to 16
```

## Statistics

Account-wide analytics (requires authentication):

```python
from spoo import GroupBy, Metric, StatsFilter

stats = client.stats.query(
    start_date="2026-07-01",
    end_date="2026-08-19",
    group_by=[GroupBy.TIME, GroupBy.COUNTRY, GroupBy.DEVICE, GroupBy.UTM_SOURCE],
    metrics=[Metric.CLICKS, Metric.UNIQUE_CLICKS],
    timezone="Asia/Kolkata",
    filters=StatsFilter(country=["IN", "US"], utm_campaign=["launch"]),
)
print(stats.summary.total_clicks)
for row in stats.metrics["clicks_by_country"]:   # "{metric}_by_{dimension}"
    print(row)
```

For a single link you own:

```python
stats = client.stats.for_link(url.id, group_by=[GroupBy.TIME])
```

Public per-link stats work without authentication. Password-protected links take the password in a POST body, never in the URL:

```python
public = client.stats.public("mylink")
public = client.stats.public("mylink", password="Secret@123")
```

### Exports

Same parameters as `query()`, in `csv`, `xlsx`, `json`, or `xml`. The return value is `bytes` plus the server's suggested `filename` and `content_type`:

```python
from pathlib import Path
from spoo import ExportFormat

data = client.stats.export(ExportFormat.CSV, start_date="2026-07-01")
Path(data.filename or "report.csv").write_bytes(data)   # server names the file

link_data = client.stats.export_link(url.id, ExportFormat.XLSX)
Path(link_data.filename or "link.xlsx").write_bytes(link_data)
```

## Sign in with Spoo

For connected apps: the PKCE device-auth flow gets you user-scoped tokens without handling passwords. Your app must be registered with spoo.me.

```python
client = SpooClient()
pkce = client.oauth.generate_pkce()
state = client.oauth.generate_state()

# 1. Send the user to the consent page
print(client.oauth.authorization_url("my-app", code_challenge=pkce.challenge, state=state))

# 2. Your redirect URI receives code + state; verify state, then exchange
tokens = client.oauth.exchange_code(code, pkce.verifier)
print(tokens.user.email)

# 3. A provider keeps the session fresh (refresh tokens rotate: persist them)
provider = client.oauth.token_provider(tokens, on_refresh=save_to_disk)
user_client = SpooClient(bearer_token=provider)
print(user_client.me().plan)
```

When the refresh token itself is rejected, calls raise `SessionExpiredError`: send the user through the flow again. See [examples/sign_in_with_spoo.py](examples/sign_in_with_spoo.py) for the full loop.

## Error handling

Errors map to typed exceptions carrying the backend error code:

| Status | Exception |
| --- | --- |
| 400 / 422 | `ValidationError` |
| 401 | `AuthenticationError` |
| 403 | `ForbiddenError` |
| 404 | `NotFoundError` |
| 409 | `ConflictError` |
| 410 | `GoneError` |
| 413 | `PayloadTooLargeError` |
| 429 | `RateLimitError` (`retry_after`, `limit`, `remaining`, `reset`) |
| 451 | `ContentBlockedError` (the link was taken down for safety) |
| 503 | `ServiceUnavailableError` |
| other 5xx | `InternalServerError` |

Network failures raise `APIConnectionError` / `APITimeoutError`; a rejected refresh token raises `SessionExpiredError`. All of them subclass `SpooError`.

```python
from spoo import RateLimitError, ValidationError

try:
    client.shorten("https://example.com", alias="taken")
except ValidationError as e:
    print(e.error_code, e.message)
except RateLimitError as e:
    print(f"limited, window resets at {e.reset}")
```

## Scope

The SDK covers the data plane a third-party integration builds against: links (create, manage, bulk, claim, emoji aliases), analytics (account, per-link, public, exports), the public preview, and Sign in with Spoo plus the read-only identity check.

Deliberately out of scope: API key management, account and profile lifecycle, `/contact`, `/health`, and all legacy (pre-v1) endpoints. Feature-gated surfaces (custom domains management, webhooks, geo rules, meta tags) are not wrapped while they are not generally available, except the `domain` parameters which pass through.

| Method | Endpoint |
| --- | --- |
| `shorten`, `urls.create` | `POST /api/v1/shorten` |
| `urls.check_alias` | `GET /api/v1/shorten/check-alias` |
| `urls.list`, `urls.list_page` | `GET /api/v1/urls` |
| `urls.get` | `GET /api/v1/urls/{url_id}` |
| `urls.get_by_alias` | `GET /api/v1/urls/{domain}/{alias}` |
| `urls.update`, `urls.set_status`, `urls.delete` | `PATCH`/`DELETE /api/v1/urls/{url_id}` |
| `urls.delete_all` | `DELETE /api/v1/urls?domain=` |
| `urls.claim`, `urls.claim_many` | `POST /api/v1/urls/claim` |
| `urls.bulk_*` | `POST /api/v1/urls/bulk/{delete,status,expiry,domain}` |
| `urls.preview` | `GET /api/v1/public/preview/{short_code}` |
| `urls.emoji_set` | `GET /api/v1/emoji-set` |
| `stats.query`, `stats.for_link` | `GET /api/v1/stats`, `/api/v1/stats/links/{url_id}` |
| `stats.public` | `GET`/`POST /api/v1/public/stats/{short_code}` |
| `stats.export`, `stats.export_link` | `GET /api/v1/export`, `/api/v1/export/links/{url_id}` |
| `oauth.*` | `/auth/device/{token,refresh}` |
| `me` | `GET /auth/me` |

For anything not listed, `client.request(method, path, params=, json=)` is the supported escape hatch: it applies the client's auth, retries, and error mapping, and returns the parsed JSON. If you need it, the surface has a gap worth [filing](https://github.com/spoo-me/spoo-py/issues).

## Retries and configuration

Retries (default 2) honor `Retry-After` and back off exponentially with jitter. GET/PUT/DELETE retry on 408/429/5xx and network failures; POST/PATCH retry only on 429 and 503, where the server provably did no work.

```python
client = SpooClient(
    api_key="spoo_...",
    base_url="https://your-instance/api/v1",
    timeout=30.0,
    max_retries=3,
    default_headers={"X-Request-ID": "..."},
)
```

Every request carries an `X-Spoo-Client: sdk-py/<version>` tag; override it via `default_headers` if you are building a product on top and want traffic attributed to it.

Note on custom domains: `domain=` parameters work end to end, but custom domains are currently in a limited beta on spoo.me, so most accounts will see `403` until it opens up.

## Examples

Runnable scripts in [examples/](examples/): quickstart, async usage, analytics, URL management, claim links, emoji aliases, and Sign in with Spoo.

## Development

```bash
uv sync
uv run pytest
uv run ruff check src/ tests/ examples/
uv run mypy --strict src/spoo/
```

## Versioning

Response models tolerate new fields (`extra="allow"`), so additive API changes never break an installed version. Breaking changes bump the major version.

## License

[MIT](LICENSE)
