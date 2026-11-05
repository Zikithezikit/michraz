from collections.abc import Iterator

import pytest

from michraz import Tender
from michraz.sources import BUILT_IN, BaseSource, Source, SourceName, default_sources
from tests.helpers import make_tender


class ListSource(BaseSource[dict[str, str]]):
    name = "list"
    description = "records from a list"
    attribution = "test"

    def __init__(self, records: list[dict[str, str]]) -> None:
        super().__init__(cache_dir=None)
        self._records = records

    def records(self) -> Iterator[dict[str, str]]:
        return iter(self._records)

    def record_id(self, record: dict[str, str]) -> object:
        return record.get("id")

    def parse(self, record: dict[str, str]) -> Tender:
        return make_tender(source=self.name, source_id=record["id"], title=record["title"])


def test_fetch_parses_every_record():
    source = ListSource([{"id": "1", "title": "a"}, {"id": "2", "title": "b"}])
    assert [t.source_id for t in source.fetch()] == ["1", "2"]
    assert source.errors == []


def test_fetch_skips_and_reports_records_that_cannot_be_parsed():
    source = ListSource([{"id": "1", "title": "a"}, {"id": "2"}, {"id": "3", "title": "c"}])
    assert [t.source_id for t in source.fetch()] == ["1", "3"]
    assert len(source.errors) == 1 and "'2'" in source.errors[0] and "KeyError" in source.errors[0]


def test_fetch_drops_repeated_tenders():
    source = ListSource([{"id": "1", "title": "a"}, {"id": "1", "title": "again"}])
    assert [t.title for t in source.fetch()] == ["a"]


def test_errors_start_empty_on_every_fetch():
    source = ListSource([{"id": "2"}])
    list(source.fetch())
    source._records = [{"id": "1", "title": "a"}]
    list(source.fetch())
    assert source.errors == []


def test_a_source_without_records_or_parse_cannot_be_created():
    class Incomplete(BaseSource[str]):
        name = "x"

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


@pytest.mark.parametrize("cls", BUILT_IN, ids=lambda c: c.name)
def test_every_built_in_source_follows_the_same_contract(cls):
    assert issubclass(cls, BaseSource)
    assert cls.name in {n.value for n in SourceName} and type(cls.name) is str
    assert cls.description and cls.attribution
    source = cls(cache_dir=None)
    assert isinstance(source, Source) and source.errors == []


def test_default_sources_follow_the_registry_order():
    assert [type(s) for s in default_sources(cache_dir=None)] == list(BUILT_IN)
