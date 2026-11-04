"""Add your own source. Any class with these members works; no network is involved in this example."""

from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

from michraz import Michraz, Tender

JERUSALEM = ZoneInfo("Asia/Jerusalem")


class DemoCitySource:
    name = "demo-city"
    description = "A made-up municipality"
    attribution = "Demo City, example data"

    def __init__(self) -> None:
        self.errors: list[str] = []  # message for every record you skip

    def fetch(self) -> Iterator[Tender]:
        yield Tender(
            source=self.name,
            source_id="2026-1",
            title="מכרז לדוגמה",
            number="1/2026",
            publisher="עיריית דמו",
            deadline=datetime(2999, 1, 1, 12, 0, tzinfo=JERUSALEM),
            attribution=self.attribution,
        )


if __name__ == "__main__":
    with Michraz([DemoCitySource()], cache_dir=None) as m:
        for tender in m.search(open_only=True):
            print(tender.number, tender.title, tender.deadline.isoformat())
