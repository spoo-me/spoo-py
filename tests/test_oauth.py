from __future__ import annotations

import base64
import json
import time

import httpx
import pytest
import respx

from spoo import SessionExpiredError, SpooClient, generate_pkce_pair, generate_state
from spoo.types.oauth import OAuthTokens

# RFC 7636 Appendix B reference vector
RFC7636_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
RFC7636_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def make_jwt(exp: float | None) -> str:
    payload: dict = {"sub": "u1"}
    if exp is not None:
        payload["exp"] = exp
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJIUzI1NiJ9.{body}.sig"


def test_pkce_challenge_matches_rfc7636_vector():
    import hashlib

    digest = hashlib.sha256(RFC7636_VERIFIER.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    assert challenge == RFC7636_CHALLENGE


def test_pkce_pair_shape():
    pair = generate_pkce_pair()
    assert len(pair.verifier) == 43
    assert set(pair.verifier) <= set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )
    assert len(pair.challenge) == 43
    assert generate_state() != generate_state()


def test_authorization_url():
    client = SpooClient(base_url="https://spoo.me/api/v1")
    url = client.oauth.authorization_url(
        "my-app", code_challenge="CHAL", state="STATE", redirect_uri="http://localhost:8000/cb"
    )
    assert url.startswith("https://spoo.me/auth/device/login?")
    assert "app_id=my-app" in url
    assert "code_challenge=CHAL" in url
    assert "code_challenge_method=S256" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcb" in url

    no_redirect = client.oauth.authorization_url("my-app", code_challenge="C", state="S")
    assert "redirect_uri" not in no_redirect


def test_exchange_code_wire(mock_site, sync_client):
    route = mock_site.post("/auth/device/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": make_jwt(time.time() + 900),
                "refresh_token": "rt1",
                "user": {"id": "u1", "email": "a@b.c"},
            },
        )
    )
    tokens = sync_client.oauth.exchange_code("CODE", "VERIFIER")
    body = json.loads(route.calls[0].request.content)
    assert body == {"code": "CODE", "code_verifier": "VERIFIER"}
    # code + verifier are the credentials: no Authorization header
    assert "authorization" not in route.calls[0].request.headers
    assert tokens.user is not None and tokens.user.id == "u1"


def test_refresh_rejection_maps_to_session_expired(mock_site, sync_client):
    mock_site.post("/auth/device/refresh").mock(
        return_value=httpx.Response(401, json={"error": "bad refresh", "code": "invalid_token"})
    )
    with pytest.raises(SessionExpiredError):
        sync_client.oauth.refresh_tokens("dead")


def test_token_provider_serves_and_rotates(mock_site):
    plain = SpooClient(base_url="https://spoo.me/api/v1")
    fresh = make_jwt(time.time() + 900)
    expired = make_jwt(time.time() - 10)
    rotated: list[OAuthTokens] = []

    mock_site.post("/auth/device/refresh").mock(
        return_value=httpx.Response(200, json={"access_token": fresh, "refresh_token": "rt2"})
    )
    provider = plain.oauth.token_provider(
        OAuthTokens(access_token=expired, refresh_token="rt1"),
        on_refresh=rotated.append,
    )
    assert provider() == fresh  # expired -> refreshed
    assert provider() == fresh  # cached now, no second refresh
    assert len(rotated) == 1
    assert rotated[0].refresh_token == "rt2"
    assert provider.tokens.refresh_token == "rt2"

    provider.invalidate()  # force refresh on next call
    assert provider() == fresh
    assert len(rotated) == 2


def test_token_provider_unparseable_exp_never_proactively_refreshes(mock_site):
    plain = SpooClient(base_url="https://spoo.me/api/v1")
    provider = plain.oauth.token_provider(
        OAuthTokens(access_token="not-a-jwt", refresh_token="rt1")
    )
    assert provider() == "not-a-jwt"  # no refresh route mocked: would error if called


def test_dynamic_bearer_resolved_per_request(mock_api):
    calls: list[int] = []

    def provider() -> str:
        calls.append(1)
        return f"tok-{len(calls)}"

    client = SpooClient(bearer_token=provider, base_url="https://spoo.me/api/v1")
    mock_api.get("/urls/abc").mock(
        return_value=httpx.Response(200, json={"id": "abc", "password_set": False})
    )
    client.urls.get("abc")
    client.urls.get("abc")
    assert len(calls) == 2
    assert mock_api.calls[1].request.headers["Authorization"] == "Bearer tok-2"


def test_me_unwraps_envelope(mock_site, sync_client):
    mock_site.get("/auth/me").mock(
        return_value=httpx.Response(
            200, json={"user": {"id": "u1", "email": "a@b.c", "plan": "free"}}
        )
    )
    user = sync_client.me()
    assert user.id == "u1"
    assert user.plan == "free"


@pytest.mark.asyncio
async def test_async_token_provider(mock_site):
    from spoo import AsyncSpooClient

    fresh = make_jwt(time.time() + 900)
    expired = make_jwt(time.time() - 10)
    mock_site.post("/auth/device/refresh").mock(
        return_value=httpx.Response(200, json={"access_token": fresh, "refresh_token": "rt2"})
    )
    plain = AsyncSpooClient(base_url="https://spoo.me/api/v1")
    seen: list[OAuthTokens] = []

    async def persist(t: OAuthTokens) -> None:
        seen.append(t)

    provider = plain.oauth.token_provider(
        OAuthTokens(access_token=expired, refresh_token="rt1"), on_refresh=persist
    )
    assert await provider() == fresh
    assert seen[0].refresh_token == "rt2"

    authed = AsyncSpooClient(bearer_token=provider, base_url="https://spoo.me/api/v1")
    with respx.mock(base_url="https://spoo.me/api/v1") as api:
        api.get("/urls/abc").mock(
            return_value=httpx.Response(200, json={"id": "abc", "password_set": False})
        )
        await authed.urls.get("abc")
        assert api.calls[0].request.headers["Authorization"] == f"Bearer {fresh}"
