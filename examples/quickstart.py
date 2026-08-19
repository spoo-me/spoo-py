"""Shorten a URL and read back its stats.

Run: python examples/quickstart.py
Set SPOO_API_KEY to run authenticated; anonymous works under anon limits.
"""

from spoo import SpooClient


def main() -> None:
    with SpooClient() as client:
        url = client.shorten("https://example.com")
        print(f"short url : {url.short_url}")
        print(f"alias     : {url.alias}")
        print(f"status    : {url.status}")

        stats = client.stats.public(url.alias)
        print(f"clicks    : {stats.stats.summary.total_clicks}")


if __name__ == "__main__":
    main()
