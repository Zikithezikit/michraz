from datetime import timedelta

import pytest

from michraz import BidsSource, SourceFormatError, SourceUnavailableError, TenderKind, default_sources
from michraz.sources import BUILT_IN, BidsExtra, SourceName
from michraz.sources.bids import Cell, Table, parse_tables
from tests.helpers import CITIES as CITY_CLASSES
from tests.helpers import FIXTURES, at

CITIES = {c.name: c for c in CITY_CLASSES}


def page(key: str) -> str:
    return (FIXTURES / f"bids_{key}.html").read_text(encoding="utf-8")


def fetch(respx_mock, http, key: str, body: str | None = None):
    city = CITIES[key]
    respx_mock.get(city.url).respond(text=body if body is not None else page(key))
    source = city()
    source.bind(http)
    return source, list(source.fetch())


@pytest.mark.parametrize("key", sorted(CITIES))
def test_every_layout_parses_without_errors(respx_mock, http, key):
    source, tenders = fetch(respx_mock, http, key)
    assert tenders and not source.errors
    assert all(t.title and t.source_id and t.publisher == CITIES[key].publisher for t in tenders)
    assert all(t.source == key and CITIES[key].domain in t.attribution for t in tenders)


def test_basic_fields_and_end_of_day_deadline(respx_mock, http):
    _, tenders = fetch(respx_mock, http, "kfar-saba")
    t = next(t for t in tenders if t.source_id == "663")
    assert t.title == "מכרז פומבי 139/26 - מנהל/ת מועדון גימלאים כיסופים"
    assert t.url == "https://www.kfar-saba.muni.il/bids/?id=663"
    assert t.extra[BidsExtra.TYPE] == "פומבי"
    assert (t.published_at.day, t.published_at.hour) == (28, 0)
    assert (t.deadline.month, t.deadline.day, t.deadline.hour, t.deadline.minute) == (11, 12, 23, 59)
    assert t.deadline.utcoffset() == timedelta(hours=2)


def test_a_tender_is_open_through_its_last_day(respx_mock, http):
    _, tenders = fetch(respx_mock, http, "kfar-saba")
    t = next(t for t in tenders if t.source_id == "663")
    assert t.is_open(at(2026, 11, 12, 18, 0))
    assert not t.is_open(at(2026, 11, 13, 0, 1))


@pytest.mark.parametrize("key", ["akko", "kiryat-motzkin", "betshemesh"])
def test_labels_meant_for_mobile_screens_are_not_part_of_the_text(respx_mock, http, key):
    _, tenders = fetch(respx_mock, http, key)
    assert not any(t.title.startswith("שם המכרז") for t in tenders)
    assert all(t.deadline is not None for t in tenders)


def test_a_void_element_with_a_hiding_class_does_not_hide_the_page(respx_mock, http):
    _, tenders = fetch(respx_mock, http, "nof-hagalil")
    assert tenders and all(t.title for t in tenders)


def test_category_column_is_kept(respx_mock, http):
    _, tenders = fetch(respx_mock, http, "kiryat-motzkin")
    assert {t.extra[BidsExtra.CATEGORY] for t in tenders} == {"מכרזים"}


def test_rows_without_an_item_id_use_the_tender_number(respx_mock, http):
    _, tenders = fetch(respx_mock, http, "dimona")
    t = tenders[0]
    assert t.source_id == t.number == "68/26"
    assert t.url.endswith(".pdf")


def test_missing_deadline_is_none(respx_mock, http):
    _, tenders = fetch(respx_mock, http, "nof-hagalil")
    assert all(t.deadline is None for t in tenders) and not any(t.is_open() for t in tenders)


def test_language_prefixed_pages_are_requested_where_they_live():
    assert CITIES["akko"].url == "https://www.akko.muni.il/he/bids/"
    assert CITIES["tamra"].url == "https://www.tamra.muni.il/ar/bids/"


def test_a_row_without_a_title_is_skipped_and_reported(respx_mock, http):
    body = page("kfar-saba").replace("<strong>מכרז פומבי 139/26 - מנהל/ת מועדון גימלאים כיסופים</strong>", "")
    source, tenders = fetch(respx_mock, http, "kfar-saba", body)
    assert "663" not in {t.source_id for t in tenders}
    assert len(source.errors) == 1


def test_a_tender_in_two_tables_is_returned_once(respx_mock, http):
    body = page("yavne") + page("yavne")
    _, tenders = fetch(respx_mock, http, "yavne", body)
    assert len(tenders) == len({t.source_id for t in tenders})


def test_page_without_a_bids_table_raises_format_error(respx_mock, http):
    city = CITIES["arad"]
    respx_mock.get(city.url).respond(text="<html>moved</html>")
    source = city()
    source.bind(http)
    with pytest.raises(SourceFormatError):
        list(source.fetch())


def test_server_error_raises_unavailable(respx_mock, http):
    city = CITIES["arad"]
    respx_mock.get(city.url).respond(status_code=503)
    source = city()
    source.bind(http)
    with pytest.raises(SourceUnavailableError):
        list(source.fetch())


def test_parse_tables_ignores_tables_that_are_not_bids_tables():
    tables = parse_tables("<table><tr><th>x</th></tr></table><table class='bids'><tr><th>y</th></tr></table>")
    assert [(t.headers, t.rows) for t in tables] == [(["y"], [])]


def test_registry_is_consistent():
    names = [c.name for c in BUILT_IN]
    assert names == [n.value for n in SourceName]
    assert len(names) == len(set(names))
    for city in CITY_CLASSES:
        assert city.domain == f"www.{city.name}.muni.il" and city.publisher and city.path.endswith("/bids/")
        assert city.url == f"https://{city.domain}{city.path}"
        assert city.publisher in city.attribution and city.domain in city.description
    assert "azor" not in names  # its robots.txt disallows every path
    assert [s.name for s in default_sources()] == names


def test_the_base_class_cannot_be_used_directly():
    with pytest.raises(TypeError):
        BidsSource()


@pytest.mark.parametrize(
    ("key", "source_id", "kind"),
    [
        ("kfar-saba", "663", TenderKind.VACANCY),  # table captioned "human resources tenders"
        ("kfar-saba", "662", TenderKind.TENDER),  # table captioned "calls for proposals"
        ("dimona", "68/26", TenderKind.VACANCY),  # table captioned "manpower"
        ("betshemesh", "3312", TenderKind.VACANCY),  # table captioned "HR tenders"
        ("yavne", "177", TenderKind.TENDER),  # external investment-management tender
        ("nof-hagalil", "1923", TenderKind.TENDER),
    ],
)
def test_staff_vacancies_are_told_apart_from_tenders(respx_mock, http, key, source_id, kind):
    _, tenders = fetch(respx_mock, http, key)
    assert next(t for t in tenders if t.source_id == source_id).kind == kind


def test_a_vacancy_is_recognized_by_its_title_when_the_table_has_no_caption():
    source = CITIES["savyon"]()
    table = Table(caption="", headers=["שם המכרז"], rows=[])
    job = source.parse((table, [Cell("מכרז חיצוני 12/26 מנהל/ת מחלקה", "?id=1")]))
    ad = source.parse((table, [Cell("מודעת דרושים D1-26 סייעת", "?id=2")]))
    work = source.parse((table, [Cell("מכרז פומבי 12/26 עבודות גינון", "?id=3")]))
    assert (job.kind, ad.kind, work.kind) == (TenderKind.VACANCY, TenderKind.VACANCY, TenderKind.TENDER)


def test_the_caption_is_read_even_when_the_site_hides_it():
    tables = parse_tables('<table class="bids"><caption class="sr-only">דרושים</caption><tr><th>x</th></tr></table>')
    assert tables[0].caption == "דרושים"
