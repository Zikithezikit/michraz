import csv
import io
import json
import sys

import pytest

from michraz import Document, to_csv, to_dataframe, to_dicts
from michraz.export import CSV_COLUMNS
from tests.helpers import at, make_tender

HEBREW = 'מכרז "גינון", שיקום ותחזוקה'


def sample():
    return [
        make_tender(
            source="beersheva",
            source_id="896",
            title=HEBREW,
            number="33/2026",
            publisher="עיריית באר שבע",
            deadline=at(2026, 11, 10, 12),
            url="http://example.test/896",
            documents=(Document("מפרט", "http://example.test/a.pdf"),),
            attribution="credit line",
            extra={"raw": {"big": "record"}, "payment_url": None, "committee_at": at(2026, 11, 1)},
        ),
        make_tender(source_id="2", title="no deadline", winner="Acme"),
    ]


def test_csv_round_trip_keeps_hebrew_and_commas(tmp_path):
    path = tmp_path / "out.csv"
    assert to_csv(sample(), path) == 2
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0]) == CSV_COLUMNS
    assert rows[0]["title"] == HEBREW
    assert rows[0]["publisher"] == "עיריית באר שבע"
    assert rows[0]["deadline"] == "2026-11-10T12:00:00+02:00"
    assert rows[0]["attribution"] == "credit line"
    assert rows[1]["deadline"] == "" and rows[1]["winner"] == "Acme"


def test_csv_file_starts_with_a_byte_order_mark(tmp_path):
    path = tmp_path / "out.csv"
    to_csv(sample(), path)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_csv_to_an_open_file():
    buffer = io.StringIO()
    assert to_csv(sample(), buffer) == 2
    assert buffer.getvalue().splitlines()[0] == ",".join(CSV_COLUMNS)


def test_csv_neutralizes_spreadsheet_formulas():
    buffer = io.StringIO()
    to_csv([make_tender(title='=HYPERLINK("http://evil")', number="+1", winner="@x")], buffer)
    row = list(csv.DictReader(io.StringIO(buffer.getvalue())))[0]
    assert row["title"].startswith("'=") and row["number"] == "'+1" and row["winner"] == "'@x"


def test_csv_of_nothing_is_just_the_header():
    buffer = io.StringIO()
    assert to_csv([], buffer) == 0
    assert buffer.getvalue().strip() == ",".join(CSV_COLUMNS)


def test_to_dicts_is_json_serializable_and_drops_raw_by_default():
    dicts = to_dicts(sample())
    json.dumps(dicts, ensure_ascii=False)
    assert dicts[0]["deadline"] == "2026-11-10T12:00:00+02:00"
    assert dicts[0]["documents"] == [{"title": "מפרט", "url": "http://example.test/a.pdf"}]
    assert "raw" not in dicts[0]["extra"]
    assert dicts[0]["extra"]["committee_at"] == "2026-11-01T00:00:00+02:00"
    assert dicts[1]["deadline"] is None


def test_to_dicts_can_keep_raw():
    assert to_dicts(sample(), include_raw=True)[0]["extra"]["raw"] == {"big": "record"}


def test_to_dataframe_has_real_datetimes():
    pandas = pytest.importorskip("pandas")
    frame = to_dataframe(sample())
    assert len(frame) == 2
    assert pandas.api.types.is_datetime64_any_dtype(frame["deadline"])


def test_to_dataframe_explains_the_missing_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "pandas", None)
    with pytest.raises(ImportError, match=r"michraz\[pandas\]"):
        to_dataframe(sample())
