from collections.abc import Iterator
from datetime import date

import pytest

from michraz import Michraz, RmiSource, SourceUnavailableError, Tender
from michraz.sources.beersheva import API_URL
from michraz.sources.rmi import SEARCH_URL
from tests.helpers import at, ckan, make_tender


class FakeSource:
    description = "fake"
    attribution = "fake credit"

    def __init__(self, name: str, tenders: list[Tender], errors: list[str] | None = None) -> None:
        self.name = name
        self._tenders = tenders
        self.errors = errors or []

    def fetch(self) -> Iterator[Tender]:
        yield from self._tenders


@pytest.fixture
def served(respx_mock, rmi_records, bs_records):
    respx_mock.post(SEARCH_URL).respond(json=rmi_records)
    respx_mock.get(API_URL).respond(json=ckan(bs_records))


def test_searches_every_default_source_sorted_by_deadline(served):
    with Michraz(cache_dir=None) as m:
        tenders = m.search()
    assert {t.source for t in tenders} == {"rmi", "beersheva"}
    deadlines = [t.deadline for t in tenders if t.deadline]
    assert deadlines == sorted(deadlines)
    assert all(t.deadline is None for t in tenders[len(deadlines) :])


def test_keyword_filters_across_sources(served):
    with Michraz(cache_dir=None) as m:
        found = m.search(keyword="גינון")
    assert found and all("גינון" in t.title for t in found)


def test_open_only_drops_closed_tenders(served):
    with Michraz(cache_dir=None) as m:
        everything = m.search()
        open_now = m.search(open_only=True)
    assert len(open_now) < len(everything)
    assert all(t.is_open() for t in open_now)
    assert not any(t.winner for t in open_now)


def test_source_argument_limits_the_fetch(respx_mock, rmi_records):
    route = respx_mock.post(SEARCH_URL).respond(json=rmi_records)
    with Michraz(cache_dir=None) as m:
        tenders = m.search(source="rmi")
    assert {t.source for t in tenders} == {"rmi"} and route.call_count == 1


def test_unknown_source_is_a_value_error():
    with Michraz(cache_dir=None) as m, pytest.raises(ValueError, match="unknown source 'nope'.*rmi, beersheva"):
        m.search(source="nope")


def test_closing_window(served):
    with Michraz(cache_dir=None) as m:
        window = m.search(closing_after=date(2026, 12, 1), closing_before=date(2026, 12, 29))
    assert window and all(t.deadline.month == 12 for t in window)


def test_custom_sources_and_error_collection():
    early = make_tender(source="fake", source_id="1", deadline=at(2026, 12, 1))
    undated = make_tender(source="fake", source_id="2")
    other = make_tender(source="other", source_id="3", deadline=at(2026, 11, 20))
    sources = [FakeSource("fake", [undated, early], ["fake: skipped record 9"]), FakeSource("other", [other])]
    with Michraz(sources, cache_dir=None) as m:
        assert [t.source_id for t in m.search()] == ["3", "1", "2"]
        assert m.last_errors == ["fake: skipped record 9"]
        m.search(source="other")
        assert m.last_errors == []


def test_duplicate_source_names_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        Michraz([FakeSource("a", []), FakeSource("a", [])], cache_dir=None)


def test_interval_floor_is_enforced():
    with pytest.raises(ValueError, match="0.5"):
        Michraz(min_interval=0.1)


def test_sources_share_the_facade_client(served):
    rmi = RmiSource()
    with Michraz([rmi], cache_dir=None) as m:
        assert rmi._http is m._http


def test_a_source_that_is_down_raises(respx_mock):
    respx_mock.post(SEARCH_URL).respond(404)
    with Michraz(cache_dir=None) as m, pytest.raises(SourceUnavailableError):
        m.search()


def test_second_search_uses_the_cache(respx_mock, rmi_records, tmp_path):
    route = respx_mock.post(SEARCH_URL).respond(json=rmi_records)
    with Michraz([RmiSource()], cache_dir=tmp_path) as m:
        m.search()
        m.search()
    assert route.call_count == 1


def test_repr_lists_source_names():
    with Michraz(cache_dir=None) as m:
        assert repr(m) == "Michraz(sources=['rmi', 'beersheva'])"


def test_base_source_is_abstract():
    from michraz.sources import BaseSource

    with pytest.raises(TypeError):
        BaseSource()  # type: ignore[abstract]
