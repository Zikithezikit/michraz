"""End-to-end flows through the public surface with the services replaced by recorded responses."""

import csv
import json
import subprocess
import sys

import pytest

from michraz import Michraz, to_csv, to_dicts
from michraz.cli import main
from michraz.sources.beersheva import API_URL
from michraz.sources.rmi import SEARCH_URL
from tests.helpers import ckan


@pytest.fixture
def services(respx_mock, rmi_records, bs_records):
    rmi = respx_mock.post(SEARCH_URL).respond(json=rmi_records)
    beersheva = respx_mock.get(API_URL).respond(json=ckan(bs_records))
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
    with Michraz(cache_dir=None) as m:
        tenders = m.search()
    assert len(tenders) == len(rmi_records) + len(bs_records)
    assert len(m.last_errors) == 2


def test_module_entry_point_runs():
    done = subprocess.run([sys.executable, "-m", "michraz", "--version"], capture_output=True, text=True, check=True)
    assert done.stdout.startswith("michraz ")
