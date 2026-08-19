"""Async client usage: concurrent shortening with asyncio.

Run: python examples/async_usage.py
"""

import asyncio

from spoo import AsyncSpooClient

URLS = [
    "https://example.com/docs",
    "https://example.com/blog",
    "https://example.com/pricing",
]


async def main() -> None:
    async with AsyncSpooClient() as client:
        results = await asyncio.gather(*(client.shorten(u) for u in URLS))
        for url in results:
            print(f"{url.short_url}  ->  {url.long_url}")


if __name__ == "__main__":
    asyncio.run(main())
