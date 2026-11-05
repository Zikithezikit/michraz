import csv
import json

import pytest

from michraz import __version__
from michraz.cli import main
from michraz.sources.beersheva import API_URL
from michraz.sources.gov import SEARCH_URL as GOV_URL
from michraz.sources.rmi import SEARCH_URL
from tests.helpers import GOV_EMPTY_PAGE, ckan, mock_municipalities


@pytest.fixture
def served(respx_mock, rmi_records, bs_records):
    respx_mock.post(SEARCH_URL).respond(json=rmi_records)
    respx_mock.get(API_URL).respond(json=ckan(bs_records))
    respx_mock.get(GOV_URL).respond(text=GOV_EMPTY_PAGE)
    mock_municipalities(respx_mock)


def run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_table_prints_hebrew_unreversed_with_attribution(served, capsys):
    code, out, err = run(capsys, "search", "--no-cache")
    assert code == 0
    assert out.splitlines()[0].split()[:4] == ["SOURCE", "NUMBER", "DEADLINE", "STATE"]
    assert "מתן שירותי הגברה" in out  # logical order, exactly as published
    assert "מתן שירותי הגברה"[::-1] not in out
    assert "אלפי מנשה - גבעת טל" in out
    assert "Data: Israel Land Authority" in out and "Data: Beer Sheva Municipality" in out
    assert "tenders" in out and err == ""


def test_keyword_and_source_filters(served, capsys):
    code, out, _ = run(capsys, "search", "--no-cache", "--keyword", "גינון", "--source", "beersheva")
    assert code == 0
    assert "76/2026" in out and "1 tender\n" in out and "rmi" not in out


def test_open_flag(served, capsys):
    _, out, _ = run(capsys, "search", "--no-cache", "--open")
    assert "closed" not in out and " open " in out


def test_json_output(served, capsys):
    code, out, _ = run(capsys, "search", "--no-cache", "--json", "--source", "rmi")
    data = json.loads(out)
    assert code == 0 and len(data) == 5
    assert data[0]["attribution"].startswith("Israel Land Authority")
    assert "raw" not in data[0]["extra"]
    assert "גבעת טל" in out  # not escaped to \uXXXX


def test_csv_file_is_written_and_the_table_still_prints(served, capsys, tmp_path):
    path = tmp_path / "tenders.csv"
    code, out, err = run(capsys, "search", "--no-cache", "--csv", str(path))
    assert code == 0 and "wrote 11 tenders" in err and "SOURCE" in out
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 11 and rows[0]["attribution"]


def test_skipped_records_are_reported_on_stderr(respx_mock, rmi_records, capsys):
    respx_mock.post(SEARCH_URL).respond(json=[*rmi_records, {"bad": 1}])
    code, _, err = run(capsys, "search", "--no-cache", "--source", "rmi")
    assert code == 0 and "warning: rmi: skipped record" in err


def test_service_failure_exits_1_with_a_message(respx_mock, capsys):
    respx_mock.post(SEARCH_URL).respond(404)
    code, out, err = run(capsys, "search", "--no-cache", "--source", "rmi")
    assert code == 1 and out == "" and err.startswith("michraz: error: rmi: HTTP 404")


def test_sources_command(capsys):
    code, out, _ = run(capsys, "sources", "--no-cache")
    assert code == 0
    for text in ("rmi", "beersheva", "data: Israel Land Authority", "data: Beer Sheva Municipality", "last fetch: -"):
        assert text in out


def test_sources_command_shows_cache_age(served, capsys, tmp_path, monkeypatch):
    monkeypatch.setattr("michraz.cli.DEFAULT_CACHE_DIR", tmp_path)
    main(["search", "--source", "rmi"])
    capsys.readouterr()
    _, out, _ = run(capsys, "sources")
    rmi_block, beersheva_block = out.split("beersheva")
    assert "last fetch: -" not in rmi_block and "last fetch: -" in beersheva_block


def test_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"michraz {__version__}"


def test_unknown_source_is_rejected_by_argparse(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["search", "--source", "nope"])
    assert exit_info.value.code == 2


def test_a_command_is_required(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 2


def test_whole_word_option(served, capsys):
    base = ("search", "--no-cache", "--source", "beersheva", "--keyword", "גינו")
    assert "1 tender\n" in run(capsys, *base)[1]  # part of "גינון"
    assert "0 tenders\n" in run(capsys, *base, "--whole-word")[1]
