"""Export tenders as CSV, plain dictionaries or a pandas DataFrame."""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterable
from datetime import datetime
from os import PathLike
from typing import TYPE_CHECKING, Any, TextIO

from michraz.models import Tender

if TYPE_CHECKING:
    import pandas

CSV_COLUMNS = ("source", "source_id", "number", "title", "publisher", "deadline", "winner", "url", "attribution")

# Spreadsheet programs run cells that start with one of these as formulas.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _record(tender: Tender, *, iso: bool, include_raw: bool) -> dict[str, Any]:
    convert: Callable[[Any], Any] = _iso if iso else (lambda v: v)
    extra = {
        k: convert(v) if isinstance(v, datetime) else v for k, v in tender.extra.items() if include_raw or k != "raw"
    }
    return {
        "source": tender.source,
        "source_id": tender.source_id,
        "number": tender.number,
        "title": tender.title,
        "publisher": tender.publisher,
        "published_at": convert(tender.published_at),
        "opens_at": convert(tender.opens_at),
        "deadline": convert(tender.deadline),
        "updated_at": convert(tender.updated_at),
        "winner": tender.winner,
        "url": tender.url,
        "documents": [{"title": d.title, "url": d.url} for d in tender.documents],
        "attribution": tender.attribution,
        "extra": extra,
    }


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


def _safe_cell(value: str | None) -> str:
    text = value or ""
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


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
    for t in tenders:
        writer.writerow(
            [
                _safe_cell(cell)
                for cell in (
                    t.source,
                    t.source_id,
                    t.number,
                    t.title,
                    t.publisher,
                    _iso(t.deadline),
                    t.winner,
                    t.url,
                    t.attribution,
                )
            ]
        )
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
