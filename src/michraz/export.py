"""Export tenders as CSV, plain dictionaries or a pandas DataFrame."""

from __future__ import annotations

import csv
import dataclasses
from collections.abc import Iterable, Mapping
from datetime import datetime
from os import PathLike
from typing import TYPE_CHECKING, Any, TextIO

from michraz._enums import StrEnum
from michraz.models import RAW_EXTRA_KEY, Tender

if TYPE_CHECKING:
    import pandas


class CsvColumn(StrEnum):
    """Columns of the CSV export, in order. Each value is the name of the ``Tender`` attribute it comes from."""

    SOURCE = "source"
    SOURCE_ID = "source_id"
    NUMBER = "number"
    TITLE = "title"
    PUBLISHER = "publisher"
    DEADLINE = "deadline"
    WINNER = "winner"
    URL = "url"
    ATTRIBUTION = "attribution"


CSV_COLUMNS = tuple(column.value for column in CsvColumn)

# Spreadsheet programs run cells that start with one of these as formulas.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_FORMULA_ESCAPE = "'"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _record(tender: Tender, *, iso: bool, include_raw: bool) -> dict[str, Any]:
    """Maps every field of the dataclass to a plain value, so a new field needs no change here."""
    record: dict[str, Any] = {}
    for field in dataclasses.fields(tender):
        value = getattr(tender, field.name)
        if isinstance(value, datetime):
            value = _iso(value) if iso else value
        elif isinstance(value, tuple):
            value = [dataclasses.asdict(item) for item in value]
        elif isinstance(value, Mapping):
            value = {
                str(key): (_iso(item) if iso and isinstance(item, datetime) else item)
                for key, item in value.items()
                if include_raw or key != RAW_EXTRA_KEY
            }
        record[field.name] = value
    return record


def to_dicts(tenders: Iterable[Tender], *, include_raw: bool = False) -> list[dict[str, Any]]:
    """Converts tenders to JSON-serializable dictionaries.

    Args:
        tenders: Tenders to convert.
        include_raw: Keep the untouched source record under ``extra["raw"]``. It is large, so it is off by
            default.

    Returns:
        One dictionary per tender. Datetimes are ISO 8601 strings with an offset.
    """
    return [_record(t, iso=True, include_raw=include_raw) for t in tenders]


def _safe_cell(value: object) -> str:
    text = _iso(value) if isinstance(value, datetime) else value
    text = "" if text is None else str(text)
    return _FORMULA_ESCAPE + text if text.startswith(_FORMULA_PREFIXES) else text


def to_csv(tenders: Iterable[Tender], path_or_file: str | PathLike[str] | TextIO) -> int:
    """Writes tenders to a CSV file that Excel opens correctly, Hebrew included.

    Columns are ``source, source_id, number, title, publisher, deadline, winner, url, attribution``. Text
    cells that start with ``=``, ``+``, ``-`` or ``@`` get a leading apostrophe so a spreadsheet never runs
    them as a formula.

    Args:
        tenders: Tenders to write.
        path_or_file: A path, written as UTF-8 with a byte order mark, or an open text file. For an open
            file the caller picks the encoding; use ``encoding="utf-8-sig"`` and ``newline=""`` for Excel.

    Returns:
        The number of tenders written.
    """
    if isinstance(path_or_file, (str, PathLike)):
        with open(path_or_file, "w", encoding="utf-8-sig", newline="") as handle:
            return _write_csv(tenders, handle)
    return _write_csv(tenders, path_or_file)


def _write_csv(tenders: Iterable[Tender], handle: TextIO) -> int:
    writer = csv.writer(handle)
    writer.writerow(CSV_COLUMNS)
    count = 0
    for tender in tenders:
        writer.writerow([_safe_cell(getattr(tender, column.value)) for column in CsvColumn])
        count += 1
    return count


def to_dataframe(tenders: Iterable[Tender]) -> pandas.DataFrame:
    """Converts tenders to a pandas DataFrame with real datetime columns.

    Requires the optional extra: ``pip install "michraz[pandas]"``.

    Raises:
        ImportError: If pandas is not installed.
    """
    try:
        import pandas
    except ImportError as exc:
        raise ImportError('to_dataframe needs pandas: pip install "michraz[pandas]"') from exc
    return pandas.DataFrame([_record(t, iso=False, include_raw=False) for t in tenders])
