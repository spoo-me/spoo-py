from __future__ import annotations

import pytest
import respx

from spoo import AsyncSpooClient, SpooClient

BASE_URL = "https://spoo.me/api/v1"


@pytest.fixture
def mock_api():
    with respx.mock(base_url=BASE_URL) as mock:
        yield mock


@pytest.fixture
def mock_site():
    """Mock router rooted at the site origin, for /auth/* and /health."""
    with respx.mock(base_url="https://spoo.me") as mock:
        yield mock


@pytest.fixture
def async_client():
    return AsyncSpooClient(api_key="spoo_test_key", base_url=BASE_URL)


@pytest.fixture
def sync_client():
    return SpooClient(api_key="spoo_test_key", base_url=BASE_URL)
