"""Sign in with Spoo: the PKCE device-auth flow for connected apps.

Your app is registered with spoo.me under an app_id with allowed redirect
URIs. The flow: open the consent URL in a browser, receive the code at your
redirect URI, exchange it, then let the token provider keep the session
fresh (refresh tokens rotate; persist the newest pair from on_refresh).

Run: python examples/sign_in_with_spoo.py
"""

import json
import pathlib

from spoo import OAuthTokens, SessionExpiredError, SpooClient

APP_ID = "my-app"
TOKENS_FILE = pathlib.Path("~/.config/my-app/tokens.json").expanduser()


def sign_in() -> OAuthTokens:
    client = SpooClient()
    pkce = client.oauth.generate_pkce()
    state = client.oauth.generate_state()

    url = client.oauth.authorization_url(
        APP_ID,
        code_challenge=pkce.challenge,
        state=state,
        redirect_uri="http://localhost:8912/callback",
    )
    print(f"open in a browser:\n  {url}\n")

    # In a real app your redirect URI receives ?code=...&state=...
    # Verify the state matches before exchanging.
    code = input("paste the code from the callback: ").strip()
    return client.oauth.exchange_code(code, pkce.verifier)


def persist(tokens: OAuthTokens) -> None:
    TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKENS_FILE.write_text(tokens.model_dump_json(exclude={"user"}))


def main() -> None:
    if TOKENS_FILE.exists():
        tokens = OAuthTokens.model_validate(json.loads(TOKENS_FILE.read_text()))
    else:
        tokens = sign_in()
        persist(tokens)

    bootstrap = SpooClient()
    provider = bootstrap.oauth.token_provider(tokens, on_refresh=persist)

    try:
        with SpooClient(bearer_token=provider) as client:
            user = client.me()
            print(f"signed in as {user.email} ({user.plan})")
            for item in client.links.list(page_size=5):
                print(f"  {item.alias}: {item.total_clicks or 0} clicks")
    except SessionExpiredError:
        TOKENS_FILE.unlink(missing_ok=True)
        print("session expired, run again to sign in")


if __name__ == "__main__":
    main()
