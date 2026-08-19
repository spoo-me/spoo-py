from __future__ import annotations

import os

import pytest

from spoo import AsyncSpooClient, SpooClient
from spoo._auth import ApiKeyAuth, NoAuth


def test_sync_client_init():
    client = SpooClient(api_key="spoo_test")
    assert isinstance(client._auth, ApiKeyAuth)


def test_async_client_init():
    client = AsyncSpooClient(api_key="spoo_test")
    assert isinstance(client._auth, ApiKeyAuth)


def test_client_no_auth():
    # Ensure no env var interferes
    env_backup = os.environ.pop("SPOO_API_KEY", None)
    try:
        client = SpooClient()
        assert isinstance(client._auth, NoAuth)
    finally:
        if env_backup:
            os.environ["SPOO_API_KEY"] = env_backup


def test_client_env_auth(monkeypatch):
    monkeypatch.setenv("SPOO_API_KEY", "spoo_from_env")
    client = SpooClient()
    assert isinstance(client._auth, ApiKeyAuth)


def test_client_custom_base_url():
    client = SpooClient(api_key="spoo_test", base_url="https://custom.api/v1")
    assert client._base_url == "https://custom.api/v1"


def test_client_context_manager():
    with SpooClient(api_key="spoo_test") as client:
        assert client.links is not None
        assert client.stats is not None
        assert client.oauth is not None


@pytest.mark.asyncio
async def test_async_client_context_manager():
    async with AsyncSpooClient(api_key="spoo_test") as client:
        assert client.links is not None


def test_client_has_resource_namespaces():
    client = SpooClient(api_key="spoo_test")
    assert hasattr(client, "links")
    assert hasattr(client, "stats")
    assert hasattr(client, "oauth")
    assert not hasattr(client, "urls")
    assert not hasattr(client, "exports")
    assert not hasattr(client, "api_keys")
    assert hasattr(client, "shorten")


def test_empty_api_key_forces_anonymous(monkeypatch):
    from spoo._auth import NoAuth

    monkeypatch.setenv("SPOO_API_KEY", "spoo_from_env")
    assert not isinstance(SpooClient(api_key="")._auth, NoAuth) or True
    client = SpooClient(api_key="")
    assert isinstance(client._auth, NoAuth)
