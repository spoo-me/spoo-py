from __future__ import annotations

import httpx

from ._version import __version__

DEFAULT_BASE_URL = "https://spoo.me/api/v1"
DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=5.0)
DEFAULT_MAX_RETRIES = 2
API_VERSION = "v1"
USER_AGENT = f"spoo-python/{__version__}"
CLIENT_TAG = f"sdk-py/{__version__}"
ENV_API_KEY = "SPOO_API_KEY"
ENV_BASE_URL = "SPOO_BASE_URL"

# A Retry-After above this is not worth sleeping through inline; the caller
# gets the RateLimitError immediately with retry_after intact to schedule.
MAX_HONORED_RETRY_AFTER = 60.0

RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
# POST/PATCH retry only where the server provably did no work.
NONIDEMPOTENT_RETRYABLE_STATUS_CODES = frozenset({429, 503})
MAX_RETRY_DELAY = 8.0
INITIAL_RETRY_DELAY = 0.5
