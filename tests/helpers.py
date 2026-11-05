import json
from datetime import datetime
from pathlib import Path
from typing import Any

from michraz import Tender
from michraz._dates import JERUSALEM
from michraz.sources import BUILT_IN, BidsSource

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeClock:
    """A clock whose ``sleep`` advances time instead of waiting."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def ckan(records: list[dict[str, Any]], total: int | None = None) -> dict[str, Any]:
    """Wraps rows the way the CKAN datastore API does."""
    return {"success": True, "result": {"total": len(records) if total is None else total, "records": records}}


def at(*args: int) -> datetime:
    return datetime(*args, tzinfo=JERUSALEM)


def make_tender(**overrides: Any) -> Tender:
    fields: dict[str, Any] = {"source": "test", "source_id": "1", "title": "title", "attribution": "credit"}
    fields.update(overrides)
    return Tender(**fields)


GOV_EMPTY_PAGE = "<p>נמצאו 0 תוצאות עבור ערך  במכרזים</p>"


CITIES: tuple[type[BidsSource], ...] = tuple(c for c in BUILT_IN if issubclass(c, BidsSource))

BIDS_EMPTY_PAGE = '<table class="bids"><tr><th>שם המכרז</th><th>מועד אחרון להגשה</th></tr></table>'


def mock_municipalities(respx_mock: Any) -> None:
    """Answers every municipal bids page with an empty table."""
    for city in CITIES:
        respx_mock.get(city.url).respond(text=BIDS_EMPTY_PAGE)
