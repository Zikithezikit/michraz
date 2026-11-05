"""Add your own source: subclass BaseSource, read records, turn each into a Tender. No network in this example."""

from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

from michraz import Michraz, Tender
from michraz.sources import BaseSource

JERUSALEM = ZoneInfo("Asia/Jerusalem")


class DemoCitySource(BaseSource[dict[str, str]]):
    name = "demo-city"
    description = "A made-up municipality"
    attribution = "Demo City, example data"

    def records(self) -> Iterator[dict[str, str]]:
        yield {"id": "2026-1", "title": "מכרז לדוגמה", "deadline": "2999-01-01T12:00"}
        yield {"id": "2026-2", "deadline": "2999-01-01T12:00"}  # no title: skipped and listed in errors

    def parse(self, record: dict[str, str]) -> Tender:
        return Tender(
            source=self.name,
            source_id=record["id"],
            title=record["title"],
            deadline=datetime.fromisoformat(record["deadline"]).replace(tzinfo=JERUSALEM),
            attribution=self.attribution,
        )


if __name__ == "__main__":
    with Michraz([DemoCitySource()], cache_dir=None) as m:
        for tender in m.search(open_only=True):
            print(tender.source_id, tender.title, tender.deadline.isoformat())
        print(m.last_errors)
