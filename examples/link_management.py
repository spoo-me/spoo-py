"""Manage your links: check an alias, create, list, update, delete.

Run: SPOO_API_KEY=spoo_... python examples/link_management.py
"""

from spoo import LinkFilter, LinkStatus, SortBy, SpooClient


def main() -> None:
    with SpooClient() as client:
        check = client.links.check_alias("my-campaign")
        print(f"alias available: {check.available} ({check.reason or 'ok'})")

        if check.available:
            client.links.create(
                "https://example.com/campaign",
                alias="my-campaign",
                max_clicks=1000,
                block_bots=True,
            )

        # Newest first, active only
        active = LinkFilter(status=LinkStatus.ACTIVE)
        for item in client.links.list(sort_by=SortBy.CREATED_AT, filter=active):
            print(f"{item.alias:20} {item.total_clicks or 0:>6} clicks  [{item.id}]")

        # Pause the campaign link (find its id from the list above)
        page = client.links.list_page(filter=LinkFilter(search="my-campaign"))
        if page.items:
            url_id = page.items[0].id
            client.links.set_status(url_id, LinkStatus.INACTIVE)
            print(f"paused {url_id}")


if __name__ == "__main__":
    main()
