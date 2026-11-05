"""End-to-end flows through the public surface with the services replaced by recorded responses."""

import csv
import json
import subprocess
import sys
from datetime import date

import pytest

from michraz import Michraz, to_csv, to_dicts
from michraz.cli import main
from michraz.sources.beersheva import API_URL
from michraz.sources.bids import MUNICIPALITIES
from michraz.sources.gov import SEARCH_URL as GOV_URL
from michraz.sources.rmi import SEARCH_URL
from tests.helpers import FIXTURES, GOV_EMPTY_PAGE, ckan, mock_municipalities


@pytest.fixture
def services(respx_mock, rmi_records, bs_records):
    rmi = respx_mock.post(SEARCH_URL).respond(json=rmi_records)
    beersheva = respx_mock.get(API_URL).respond(json=ckan(bs_records))
    respx_mock.get(GOV_URL).respond(text=GOV_EMPTY_PAGE)
    mock_municipalities(respx_mock)
    return rmi, beersheva


def test_search_filter_export_round_trip(services, tmp_path):
    with Michraz(cache_dir=None) as m:
        tenders = m.search(keyword="2026", open_only=True)
    assert tenders and all(t.is_open() for t in tenders)

    path = tmp_path / "open.csv"
    assert to_csv(tenders, path) == len(tenders)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [r["source_id"] for r in rows] == [t.source_id for t in tenders]
    assert {r["title"] for r in rows} == {t.title for t in tenders}
    assert all(r["attribution"] for r in rows)

    json.dumps(to_dicts(tenders), ensure_ascii=False)


def test_cli_end_to_end_with_a_warm_cache(services, tmp_path, monkeypatch, capsys):
    rmi, beersheva = services
    monkeypatch.setattr("michraz.cli.DEFAULT_CACHE_DIR", tmp_path / "cache")
    csv_path = tmp_path / "out.csv"

    assert main(["search", "--open", "--csv", str(csv_path)]) == 0
    first = capsys.readouterr().out
    assert (rmi.call_count, beersheva.call_count) == (1, 1)

    assert main(["search", "--open", "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert (rmi.call_count, beersheva.call_count) == (1, 1)  # served from the cache

    assert len(second) == first.count(" open ")
    assert {t["source"] for t in second} == {"rmi", "beersheva"}
    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_one_bad_record_does_not_kill_the_batch(respx_mock, rmi_records, bs_records):
    respx_mock.post(SEARCH_URL).respond(json=[*rmi_records, {"MichrazID": 1, "SgiraDate": "garbage"}])
    respx_mock.get(API_URL).respond(json=ckan([*bs_records, {"שם מכרז": "missing columns"}]))
    respx_mock.get(GOV_URL).respond(text=GOV_EMPTY_PAGE)
    mock_municipalities(respx_mock)
    with Michraz(cache_dir=None) as m:
        tenders = m.search()
    assert len(tenders) == len(rmi_records) + len(bs_records)
    assert len(m.last_errors) == 2


def test_module_entry_point_runs():
    done = subprocess.run([sys.executable, "-m", "michraz", "--version"], capture_output=True, text=True, check=True)
    assert done.stdout.startswith("michraz ")


@pytest.fixture
def all_services(respx_mock, rmi_records, bs_records):
    respx_mock.post(SEARCH_URL).respond(json=rmi_records)
    respx_mock.get(API_URL).respond(json=ckan(bs_records))
    respx_mock.get(GOV_URL).respond(text=(FIXTURES / "gov_search.html").read_text(encoding="utf-8"))
    mock_municipalities(respx_mock)


def test_every_default_source_contributes_and_exports(all_services, tmp_path):
    with Michraz(cache_dir=None) as m:
        tenders = m.search()
        assert m.last_errors == []
    assert {t.source for t in tenders} == {"rmi", "beersheva", "gov"}

    gov = [t for t in tenders if t.source == "gov"]
    assert len(gov) == 5
    assert all(t.url.startswith("https://mr.gov.il/") and t.publisher and t.deadline for t in gov)

    path = tmp_path / "all.csv"
    to_csv(tenders, path)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {r["source"] for r in rows} == {"rmi", "beersheva", "gov"}
    assert all("mr.gov.il" in r["attribution"] for r in rows if r["source"] == "gov")


def test_gov_keyword_and_window_filters(all_services):
    with Michraz(cache_dir=None) as m:
        hits = m.search(keyword="מנתחים", source="gov")
        window = m.search(source="gov", closing_after=date(2026, 12, 1), closing_before=date(2026, 12, 31))
    assert [t.source_id for t in hits] == ["4000623708"]
    assert window and all(date(2026, 12, 1) <= t.deadline.date() < date(2026, 12, 31) for t in window)


def test_cli_prints_government_tenders_as_json(all_services, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("michraz.cli.DEFAULT_CACHE_DIR", tmp_path / "cache")
    assert main(["search", "--source", "gov", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out) == 5 and {t["source"] for t in out} == {"gov"}
    assert all("mr.gov.il" in t["attribution"] for t in out)


@pytest.fixture
def every_service(respx_mock, rmi_records, bs_records):
    respx_mock.post(SEARCH_URL).respond(json=rmi_records)
    respx_mock.get(API_URL).respond(json=ckan(bs_records))
    respx_mock.get(GOV_URL).respond(text=(FIXTURES / "gov_search.html").read_text(encoding="utf-8"))
    for city in MUNICIPALITIES:
        body = (FIXTURES / f"bids_{city.key}.html").read_text(encoding="utf-8")
        respx_mock.get(f"https://{city.domain}{city.path}").respond(text=body)


def test_every_default_source_feeds_one_search_and_one_csv(every_service, tmp_path):
    with Michraz(cache_dir=None) as m:
        tenders = m.search()
        assert m.last_errors == []
    assert {t.source for t in tenders} == {"rmi", "beersheva", "gov", *(c.key for c in MUNICIPALITIES)}

    path = tmp_path / "everything.csv"
    to_csv(tenders, path)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(tenders) and all(r["attribution"] for r in rows)


def test_one_municipal_site_down_leaves_the_rest_of_the_search_intact(every_service, respx_mock):
    respx_mock.get(f"https://{MUNICIPALITIES[0].domain}{MUNICIPALITIES[0].path}").respond(status_code=503)
    with Michraz(cache_dir=None) as m:
        tenders = m.search()
        assert len(m.last_errors) == 1 and m.last_errors[0].startswith(f"{MUNICIPALITIES[0].key}:")
    assert MUNICIPALITIES[0].key not in {t.source for t in tenders}
    assert {"rmi", "gov", "kfar-saba"} <= {t.source for t in tenders}


def test_cli_searches_one_municipality(every_service, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("michraz.cli.DEFAULT_CACHE_DIR", tmp_path / "cache")
    assert main(["search", "--source", "kfar-saba", "--keyword", "מועדון"]) == 0
    out = capsys.readouterr().out
    assert "kfar-saba" in out and "עיריית כפר סבא" in out and "1 tender" in out
