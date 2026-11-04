import json
from datetime import datetime
from pathlib import Path
from typing import Any

from michraz import Tender
from michraz._dates import JERUSALEM

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
