import dataclasses
import json
from datetime import timedelta

from michraz import BeerShevaExtra, BeerShevaSource, RmiExtra, RmiSource, SourceName, Tender
from michraz._enums import StrEnum
from michraz._http import USER_AGENT, HttpMethod
from michraz.cli import Command, ExitCode, main
from michraz.export import CSV_COLUMNS, CsvColumn
from michraz.models import RAW_EXTRA_KEY
from michraz.sources.beersheva import API_URL
from michraz.sources.rmi import SEARCH_URL
from tests.helpers import ckan


class Sample(StrEnum):
    A = "alpha"


def test_str_enum_behaves_like_its_value():
    assert Sample.A == "alpha" and hash(Sample.A) == hash("alpha")
    assert str(Sample.A) == "alpha" and f"{Sample.A}" == "alpha" and format(Sample.A) == "alpha"
    assert {"alpha": 1}[Sample.A] == 1 and {Sample.A: 1}["alpha"] == 1
    assert json.dumps({Sample.A: Sample.A}) == '{"alpha": "alpha"}'


def test_source_names_match_the_sources_and_the_cli():
    assert RmiSource.name == SourceName.RMI and BeerShevaSource.name == SourceName.BEERSHEVA
    assert [s.value for s in SourceName] == ["rmi", "beersheva"]
    assert RmiSource.name == "rmi" and type(RmiSource.name) is str  # plain str, so custom sources need no enum


def test_rmi_extra_enum_lists_exactly_the_keys_the_source_produces(rmi_records):
    tender = RmiSource().parse(rmi_records[2])
    assert set(tender.extra) == set(RmiExtra)
    assert tender.extra[RmiExtra.REGION_CODE] == tender.extra["region_code"] == 6
    assert tender.extra[RmiExtra.RAW] is rmi_records[2]


def test_beersheva_extra_enum_lists_exactly_the_keys_the_source_produces(bs_records):
    tender = BeerShevaSource().parse(bs_records[0])
    assert set(tender.extra) == set(BeerShevaExtra)
    assert tender.extra[BeerShevaExtra.PAYMENT_URL] == tender.extra["payment_url"]


def test_raw_key_is_shared():
    assert RmiExtra.RAW == BeerShevaExtra.RAW == RAW_EXTRA_KEY == "raw"


def test_csv_columns_are_tender_attributes_in_a_fixed_order():
    assert CSV_COLUMNS == tuple(c.value for c in CsvColumn)
    fields = {f.name for f in dataclasses.fields(Tender)}
    assert {c.value for c in CsvColumn} <= fields
    assert CSV_COLUMNS == (
        "source", "source_id", "number", "title", "publisher", "deadline", "winner", "url", "attribution"
    )  # fmt: skip


def test_http_methods_and_user_agent():
    assert [m.value for m in HttpMethod] == ["GET", "POST"]
    assert USER_AGENT.startswith("michraz/")


def test_exit_codes_and_commands():
    assert (ExitCode.OK, ExitCode.ERROR) == (0, 1)
    assert [c.value for c in Command] == ["search", "sources"]


def test_enum_keys_work_end_to_end_through_the_cli(respx_mock, rmi_records, bs_records, capsys):
    respx_mock.post(SEARCH_URL).respond(json=rmi_records)
    respx_mock.get(API_URL).respond(json=ckan(bs_records))
    for name in SourceName:
        assert main([Command.SEARCH, "--no-cache", "--source", name]) == ExitCode.OK
    assert "rmi" in capsys.readouterr().out


def test_cache_age_helpers_accept_the_method_enum(respx_mock, make_http, tmp_path):
    respx_mock.get("https://example.test/x").respond(json={})
    client = make_http(cache_dir=tmp_path, cache_ttl=timedelta(minutes=1))
    client.get_json("t", "https://example.test/x")
    assert client.cached_at(HttpMethod.GET, "https://example.test/x") is not None
    assert client.cached_at("GET", "https://example.test/x") is not None  # plain strings still work
