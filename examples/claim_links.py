"""Claim anonymously created links into an account.

Anonymous shorten calls return a one-time claim_token. Hold on to it: once
the user signs in (API key or Sign in with Spoo), the token proves they
created the link and transfers ownership, stats included.

Run: SPOO_API_KEY=spoo_... python examples/claim_links.py
"""

from spoo import AsyncSpooClient, SpooClient


def main() -> None:
    # Phase 1: anonymous usage, e.g. before the user has an account.
    # api_key="" forces anonymous even when SPOO_API_KEY is set.
    with SpooClient(api_key="") as anon:
        url = anon.shorten("https://example.com/created-before-signup")
        print(f"created {url.short_url} anonymously")
        assert url.id and url.claim_token
        pending = (url.id, url.claim_token)  # persist these

    # Phase 2: the user signed in; claim what they created
    with SpooClient() as client:
        result = client.links.claim(*pending)
        print(f"claim -> {result.status}")  # claimed | already_yours | invalid

        # Batches work too (up to 16 per call)
        batch = client.links.claim_many([pending])
        print(f"batch: {batch.claimed} claimed of {len(batch.results)}")


async def async_variant() -> None:
    async with AsyncSpooClient() as client:
        url = await client.shorten("https://example.com")
        if url.claim_token:  # only present on anonymous creates
            print("claimable:", url.id)


if __name__ == "__main__":
    main()
