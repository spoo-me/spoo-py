"""Account analytics: grouped stats and a CSV export.

Run: SPOO_API_KEY=spoo_... python examples/analytics.py
"""

import pathlib

from spoo import ExportFormat, GroupBy, Metric, SpooClient


def main() -> None:
    with SpooClient() as client:
        stats = client.stats.query(
            group_by=[GroupBy.TIME, GroupBy.COUNTRY, GroupBy.BROWSER],
            metrics=[Metric.CLICKS, Metric.UNIQUE_CLICKS],
            timezone="UTC",
        )

        print(f"total clicks  : {stats.summary.total_clicks}")
        print(f"unique clicks : {stats.summary.unique_clicks}")
        print(f"first click   : {stats.summary.first_click}")
        print(f"last click    : {stats.summary.last_click}")

        # Breakdowns are keyed "{metric}_by_{dimension}"
        for row in stats.metrics.get("clicks_by_country", [])[:5]:
            print(row)

        pathlib.Path("clicks.csv").write_bytes(client.stats.export(ExportFormat.CSV))
        print("exported to clicks.csv")


if __name__ == "__main__":
    main()
