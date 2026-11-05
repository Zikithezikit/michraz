from datetime import timedelta
from urllib.parse import parse_qs

import pytest

from michraz import GovSource, SourceFormatError, SourceUnavailableError
from michraz.sources.gov import SEARCH_URL, GovExtra, parse_page
from tests.helpers import FIXTURES


@pytest.fixture
def page() -> str:
    return (FIXTURES / "gov_search.html").read_text(encoding="utf-8")


@pytest.fixture
def source(http):
    src = GovSource()
    src.bind(http)
    return src


@pytest.fixture
def by_id(respx_mock, source, page):
    respx_mock.get(SEARCH_URL).respond(text=page)
    return {t.source_id: t for t in source.fetch()}


def test_parse_page_reads_every_result_and_the_total(page):
    results, total = parse_page(page)
    assert total == 5
    assert [r["id"] for r in results][:2] == ["4000623708", "4000621860"]
    assert results[0]["type"] == "מכרז פומבי"


def test_parse_page_rejects_a_page_without_a_count():
    with pytest.raises(ValueError, match="result count"):
        parse_page("<html><body>maintenance</body></html>")


def test_basic_fields(by_id):
    t = by_id["4000623708"]
    assert (t.source, t.number) == ("gov", "10003782")
    assert t.publisher == 'משרד הבריאות - המרכז הרפואי ע"ש חיים שיבא, תל השומר'
    assert t.title.startswith("מכרז פומבי לחלוקי מנתחים")
    assert t.url == "https://mr.gov.il/ilgstorefront/he/p/4000623708"
    assert "mr.gov.il" in t.attribution
    assert t.extra[GovExtra.TYPE] == "מכרז פומבי"
    assert t.extra["status"] == "עודכן"


def test_dates_are_jerusalem_local_time(by_id):
    t = by_id["4000623708"]
    assert (t.deadline.month, t.deadline.day, t.deadline.hour) == (12, 28, 11)
    assert t.deadline.utcoffset() == timedelta(hours=2)
    assert (t.published_at.day, t.updated_at.day) == (3, 5)


def test_a_tender_listed_under_two_statuses_is_returned_once(by_id):
    assert len(by_id) == 5


def test_requests_each_open_status_with_the_archive_hidden(respx_mock, source, page):
    route = respx_mock.get(SEARCH_URL).respond(text=page)
    list(source.fetch())
    queries = [parse_qs(call.request.url.query.decode())["q"][0] for call in route.calls]
    assert [q.rsplit(":", 1)[1] for q in queries] == ["פורסם", "עודכן", "חדש"]
    assert all(q.startswith(":updateDate:archive:false:status:") for q in queries)


def test_reads_pages_until_the_total_is_reached(respx_mock, source, page):
    first = page.replace("נמצאו 5 תוצאות", "נמצאו 10 תוצאות")
    route = respx_mock.get(SEARCH_URL).respond(text=first)
    list(source.fetch())
    pages = [parse_qs(call.request.url.query.decode())["page"][0] for call in route.calls]
    assert pages[:3] == ["0", "1", "0"]


def test_a_record_without_a_title_is_skipped_and_reported(respx_mock, source, page):
    broken = page.replace("search-results-content-head", "search-results-other-class", 1)
    respx_mock.get(SEARCH_URL).respond(text=broken)
    tenders = list(source.fetch())
    assert len(tenders) == 4
    assert len(set(source.errors)) == 1 and "4000623708" in source.errors[0]


def test_a_missing_deadline_gives_none(source):
    tender = source.parse({"id": "1", "title": "t", "type": None, "fields": {}})
    assert tender.deadline is None and not tender.is_open()


def test_a_bad_date_raises(source):
    with pytest.raises(ValueError):
        source.parse({"id": "1", "title": "t", "type": None, "fields": {"מועד אחרון להגשה": "soon"}})


def test_non_search_page_raises_format_error(respx_mock, source):
    respx_mock.get(SEARCH_URL).respond(text="<html>captcha</html>")
    with pytest.raises(SourceFormatError):
        list(source.fetch())


def test_server_error_raises_unavailable(respx_mock, source):
    respx_mock.get(SEARCH_URL).respond(status_code=503)
    with pytest.raises(SourceUnavailableError):
        list(source.fetch())
