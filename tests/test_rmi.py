import json
from datetime import timedelta

import httpx
import pytest

from michraz import RmiSource, SourceFormatError, SourceUnavailableError
from michraz.sources.rmi import SEARCH_URL, settlements


@pytest.fixture
def source(http):
    src = RmiSource()
    src.bind(http)
    return src


def serve(respx_mock, records):
    return respx_mock.post(SEARCH_URL).respond(json=records)


def test_default_request_asks_for_open_tenders_only(respx_mock, source, rmi_records):
    route = serve(respx_mock, rmi_records)
    tenders = list(source.fetch())
    assert len(tenders) == len(rmi_records)
    assert json.loads(route.calls.last.request.content) == {"ActiveQuickSearch": False, "ActiveMichraz": True}


def test_first_record_is_parsed(respx_mock, source, rmi_records):
    serve(respx_mock, rmi_records)
    t = source.search()[0]
    assert (t.source, t.source_id, t.number) == ("rmi", "20170115", "115/2017")
    assert t.publisher == "רשות מקרקעי ישראל"
    assert t.url == "https://apps.land.gov.il/MichrazimSite/#/michraz/20170115"
    assert t.winner is None and t.documents == ()
    assert "apps.land.gov.il" in t.attribution


def test_dates_keep_their_offsets_and_are_aware(respx_mock, source, rmi_records):
    serve(respx_mock, rmi_records)
    t = source.search()[0]
    assert t.published_at.utcoffset() == timedelta(hours=3)  # 2017-05-11, summer time
    assert t.opens_at.utcoffset() == timedelta(hours=2)
    assert (t.deadline.month, t.deadline.day, t.deadline.hour) == (12, 28, 12)
    assert t.deadline.utcoffset() == timedelta(hours=2)
    assert t.published_at < t.opens_at < t.deadline  # an old tender re-opened years later is not a bug


def test_null_dates_become_none(respx_mock, source, rmi_records):
    serve(respx_mock, rmi_records)
    t = source.search()[0]
    assert t.extra["committee_at"] is None and t.updated_at is None


def test_leading_space_in_neighborhood_is_stripped(respx_mock, source, rmi_records):
    assert rmi_records[0]["Shchuna"] == " גבעת טל"
    serve(respx_mock, rmi_records)
    t = source.search()[0]
    assert t.extra["neighborhood"] == "גבעת טל"
    assert t.title == "אלפי מנשה - גבעת טל"


def test_extra_carries_codes_and_the_raw_record(respx_mock, source, rmi_records):
    serve(respx_mock, rmi_records)
    second = source.search()[1]
    assert second.extra["settlement"] == "מעלה אדומים"
    assert second.extra["region_code"] == 7 and second.extra["type_code"] == 9 and second.extra["purpose_code"] == 8
    assert second.extra["status_code"] == 1 and second.extra["mekuvan"] is True
    assert second.extra["housing_units"] == 0
    assert second.extra["raw"] == rmi_records[1]


def test_khal_yaad_rashi_is_exposed_raw_not_as_a_bid(respx_mock, source, rmi_records):
    serve(respx_mock, rmi_records)
    third = source.search()[2]
    assert third.extra["khal_yaad_rashi"] == 2 and "min_bid" not in third.extra


def test_unknown_settlement_falls_back_to_neighborhood_then_number(respx_mock, source, rmi_records):
    odd = dict(rmi_records[0], MichrazID=9001, KodYeshuv=999999)
    bare = dict(rmi_records[0], MichrazID=9002, KodYeshuv=999999, Shchuna=None)
    serve(respx_mock, [odd, bare])
    a, b = source.search()
    assert a.title == "גבעת טל" and a.extra["settlement"] is None
    assert b.title == "115/2017"


def test_settlement_table_is_shipped_and_sane():
    table = settlements()
    assert table[3750] == "אלפי מנשה" and table[5000] == "תל אביב יפו"
    assert len(table) > 1000


def test_server_side_filters_are_sent(respx_mock, source, rmi_records):
    route = serve(respx_mock, rmi_records[:1])
    source.search(settlement_code=3750, neighborhood="גבעת טל")
    body = json.loads(route.calls.last.request.content)
    assert body["KodYeshuv"] == 3750 and body["Shchuna"] == "גבעת טל"


def test_archive_search_turns_active_only_off(respx_mock, source, rmi_records):
    route = serve(respx_mock, rmi_records)
    source.search(active_only=False)
    assert json.loads(route.calls.last.request.content)["ActiveMichraz"] is False


def test_raw_filters_are_merged_as_is(respx_mock, source, rmi_records):
    route = serve(respx_mock, rmi_records)
    source.search(raw_filters={"Whatever": 1})
    assert json.loads(route.calls.last.request.content)["Whatever"] == 1


def test_client_side_filters(respx_mock, source, rmi_records):
    serve(respx_mock, rmi_records)
    assert [t.number for t in source.search(tender_number="509/2018")] == ["509/2018"]
    assert {t.extra["region_code"] for t in source.search(region=7)} == {7}
    assert [t.source_id for t in source.search(tender_type=9)] == ["20180509"]
    assert [t.source_id for t in source.search(purpose=8)] == ["20180509"]
    assert {t.extra["status_code"] for t in source.search(status=2)} == {2}
    assert source.search(region=7, tender_type=1) == [source.search()[0]]
    assert source.search(region=99) == []


def test_bad_record_is_skipped_and_reported(respx_mock, source, rmi_records, caplog):
    broken = [rmi_records[0], {"no": "id"}, dict(rmi_records[1], SgiraDate="garbage"), "not a dict", rmi_records[1]]
    serve(respx_mock, broken)
    with caplog.at_level("WARNING"):
        tenders = source.search()
    assert [t.source_id for t in tenders] == ["20170115", "20180509"]
    assert len(source.errors) == 3
    assert all(e.startswith("rmi: skipped record") for e in source.errors)
    assert "SgiraDate" not in source.errors[0] and "20180509" in source.errors[1]
    assert len(caplog.records) == 3


def test_errors_reset_on_each_fetch(respx_mock, source, rmi_records):
    serve(respx_mock, [{"no": "id"}])
    source.search()
    assert len(source.errors) == 1
    serve(respx_mock, rmi_records)
    source.search()
    assert source.errors == []


@pytest.mark.parametrize("payload", [{"error": "x"}, "text", 5])
def test_non_list_response_is_a_format_error(respx_mock, source, payload):
    serve(respx_mock, payload)
    with pytest.raises(SourceFormatError, match="expected a JSON list"):
        source.search()


def test_json_null_is_a_format_error(respx_mock, source):
    respx_mock.post(SEARCH_URL).respond(200, content=b"null", headers={"Content-Type": "application/json"})
    with pytest.raises(SourceFormatError, match="expected a JSON list"):
        source.search()


def test_server_error_surfaces_as_unavailable(respx_mock, source):
    respx_mock.post(SEARCH_URL).mock(return_value=httpx.Response(404))
    with pytest.raises(SourceUnavailableError, match="rmi"):
        source.search()


def test_standalone_source_builds_its_own_client(respx_mock, rmi_records, tmp_path):
    serve(respx_mock, rmi_records)
    with RmiSource(cache_dir=tmp_path) as standalone:
        assert len(standalone.search(settlement_code=3750)) == len(rmi_records)
        assert standalone.last_fetched() is None  # the cached request used a different body


def test_last_fetched_reads_the_cache(respx_mock, rmi_records, tmp_path):
    serve(respx_mock, rmi_records)
    with RmiSource(cache_dir=tmp_path) as src:
        assert src.last_fetched() is None
        list(src.fetch())
        assert src.last_fetched() is not None
