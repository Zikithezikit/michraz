from datetime import timedelta
from urllib.parse import parse_qs

import httpx
import pytest

from michraz import BeerShevaSource, SourceFormatError
from michraz.sources.beersheva import API_URL, RESOURCE_ID, parse_documents
from tests.helpers import ckan


@pytest.fixture
def source(http):
    src = BeerShevaSource()
    src.bind(http)
    return src


@pytest.fixture
def by_id(respx_mock, source, bs_records):
    respx_mock.get(API_URL).respond(json=ckan(bs_records))
    return {t.source_id: t for t in source.fetch()}


def test_basic_fields(by_id):
    t = by_id["896"]
    assert (t.source, t.number, t.publisher) == ("beersheva", "33/2026", "עיריית באר שבע")
    assert t.title.startswith("מתן שירותי הגברה")
    assert t.url.endswith("DispForm.aspx?ID=896")
    assert "data.gov.il" in t.attribution and "Other (Open)" in t.attribution


def test_deadline_is_jerusalem_local_time(by_id):
    t = by_id["896"]
    assert (t.deadline.year, t.deadline.month, t.deadline.day, t.deadline.hour) == (2026, 11, 10, 12)
    assert t.deadline.utcoffset() == timedelta(hours=2)
    assert by_id["859"].deadline.utcoffset() == timedelta(hours=3)  # 09/06/2026 is summer time
    assert t.updated_at is not None and t.updated_at.day == 29


def test_empty_winner_means_open_and_a_winner_means_closed(by_id):
    assert by_id["896"].winner is None
    assert by_id["896"].is_open(by_id["896"].deadline - timedelta(days=1))
    assert by_id["859"].winner == "עמותת בית מוריה"
    assert not by_id["859"].is_open(by_id["859"].deadline - timedelta(days=30))


def test_multi_link_files(by_id):
    docs = by_id["895"].documents
    assert len(docs) >= 2
    assert all(d.url.startswith("http://www.beer-sheva.muni.il/") and d.title for d in docs)
    assert docs[0].title.startswith("מכרז מספר 76-2026")


def test_payment_link_is_unescaped(by_id):
    assert by_id["896"].extra["payment_url"] == "https://www.paykal.co.il/br7/?post_type=product&p=106111&preview=true"
    assert by_id["859"].extra["payment_url"] is not None


def test_missing_files_column(by_id):
    assert by_id["285"].documents == ()
    assert by_id["285"].extra["payment_url"] is None


def test_html_entities_in_text_are_decoded(by_id):
    assert by_id["881"].number == "הליך קול קורא מס' 73/2026"
    assert "&#39;" not in by_id["285"].winner and "בפרק א'" in by_id["285"].winner


def test_blank_deadline_is_none(by_id):
    assert by_id["285"].deadline is None and by_id["95"].deadline is None
    assert not by_id["95"].is_open()


def test_links_without_paragraph_wrapper_and_entity_encoded_urls(by_id):
    (doc,) = by_id["95"].documents
    assert doc.url.startswith("http://www.beer-sheva.muni.il/City/FreeInfo/DocLib2/")
    assert doc.title.startswith("קול קורא - מיזם משותף")


def test_source_id_is_the_list_item_id_not_the_number(by_id):
    assert set(by_id) == {"896", "895", "859", "285", "881", "95"}


def test_extra_keeps_the_raw_row(by_id, bs_records):
    assert by_id["896"].extra["raw"] == bs_records[0]


def test_parse_documents_handles_common_shapes():
    assert parse_documents(None) == () and parse_documents("") == () and parse_documents("<p></p>") == ()
    assert parse_documents('<p>&#160;</p><img src="x.png"/>plain text') == ()
    html = '<p><a href="http://x/a?b=1&amp;c=2" target="_blank">  two\n words </a></p><a href="">dead</a><a>none</a>'
    (doc,) = parse_documents(html)
    assert doc.url == "http://x/a?b=1&c=2" and doc.title == "two words"


def test_untitled_link_uses_its_url_as_title():
    (doc,) = parse_documents('<a href="http://x/a.pdf"></a>')
    assert doc.title == "http://x/a.pdf"


def test_pagination_uses_total_and_offset(respx_mock, source, bs_records):
    source.page_size = 4
    seen = []

    def page(request: httpx.Request) -> httpx.Response:
        params = parse_qs(request.url.query.decode())
        offset, limit = int(params["offset"][0]), int(params["limit"][0])
        assert params["resource_id"] == [RESOURCE_ID]
        seen.append((offset, limit))
        return httpx.Response(200, json=ckan(bs_records[offset : offset + limit], total=len(bs_records)))

    respx_mock.get(API_URL).mock(side_effect=page)
    assert len(list(source.fetch())) == len(bs_records)
    assert seen == [(0, 4), (4, 4)]


def test_single_page_makes_a_single_request(respx_mock, source, bs_records):
    route = respx_mock.get(API_URL).respond(json=ckan(bs_records))
    list(source.fetch())
    assert route.call_count == 1


def test_pagination_stops_on_an_empty_page_even_if_total_lies(respx_mock, source, bs_records):
    route = respx_mock.get(API_URL).mock(
        side_effect=[
            httpx.Response(200, json=ckan(bs_records, total=500)),
            httpx.Response(200, json=ckan([], total=500)),
        ]
    )
    assert len(list(source.fetch())) == len(bs_records)
    assert route.call_count == 2


def test_bad_row_is_skipped_and_reported(respx_mock, source, bs_records):
    rows = [
        bs_records[0],
        dict(bs_records[1], **{"תאריך אחרון להגשה": "yesterday"}),
        {k: v for k, v in bs_records[2].items() if k != "URL"},
        dict(bs_records[2], **{"URL": "", "מספר מכרז": ""}),
        dict(bs_records[2], **{"שם מכרז": " "}),
        bs_records[2],
    ]
    respx_mock.get(API_URL).respond(json=ckan(rows))
    tenders = list(source.fetch())
    assert [t.source_id for t in tenders] == ["896", "859"]
    assert len(source.errors) == 4 and all("skipped record" in e for e in source.errors)


def test_row_without_item_id_falls_back_to_number(respx_mock, source, bs_records):
    row = dict(bs_records[0], URL="http://www.beer-sheva.muni.il/page")
    respx_mock.get(API_URL).respond(json=ckan([row]))
    assert [t.source_id for t in source.fetch()] == ["33/2026"]


@pytest.mark.parametrize(
    "payload",
    [
        {"success": False, "error": {"message": "nope"}},
        {"success": True},
        {"success": True, "result": {"records": "x", "total": 1}},
        {"success": True, "result": {"records": [], "total": "1"}},
        [],
        "oops",
    ],
)
def test_unexpected_shape_is_a_format_error(respx_mock, source, payload):
    respx_mock.get(API_URL).respond(json=payload)
    with pytest.raises(SourceFormatError, match="beersheva: not a CKAN datastore response"):
        list(source.fetch())


def test_page_size_must_be_positive():
    with pytest.raises(ValueError):
        BeerShevaSource(page_size=0)
