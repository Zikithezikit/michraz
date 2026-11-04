"""Client-side filtering and sorting of tenders."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from datetime import date, datetime, time
from typing import Final

from michraz import _dates
from michraz.models import Tender

NORMALIZATION_FORM: Final = "NFKC"

_EARLIEST = datetime.min.replace(tzinfo=_dates.JERUSALEM)


def normalize(text: str) -> str:
    """Normalizes text for matching: Unicode NFKC, then case-folded."""
    return unicodedata.normalize(NORMALIZATION_FORM, text).casefold()


def matches_keyword(tender: Tender, keyword: str) -> bool:
    """Tells whether ``keyword`` occurs in the title or the number of ``tender``.

    The match is a case-insensitive substring match on NFKC-normalized text. There is no stemming.
    """
    needle = normalize(keyword.strip())
    haystack = normalize(f"{tender.title}\n{tender.number or ''}")
    return needle in haystack


def _bound(value: datetime | date) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime bounds must be timezone-aware")
        return value
    return datetime.combine(value, time.min, tzinfo=_dates.JERUSALEM)


def apply_filters(
    tenders: Iterable[Tender],
    *,
    keyword: str | None = None,
    open_only: bool = False,
    closing_before: datetime | date | None = None,
    closing_after: datetime | date | None = None,
    now: datetime | None = None,
) -> list[Tender]:
    """Filters tenders. Every given condition must hold.

    Args:
        tenders: Tenders to filter.
        keyword: Keep tenders whose title or number contains this text.
        open_only: Keep tenders for which :meth:`Tender.is_open` is true.
        closing_before: Keep tenders whose deadline is strictly before this moment. A plain date means
            00:00 at the start of that day in Asia/Jerusalem.
        closing_after: Keep tenders whose deadline is at or after this moment. Dates are read as above.
        now: Moment used for ``open_only``. Defaults to the current time.

    Returns:
        The matching tenders in their original order. Tenders without a deadline never match a closing
        bound.

    Raises:
        ValueError: If a datetime bound or ``now`` is naive.
    """
    before = _bound(closing_before) if closing_before is not None else None
    after = _bound(closing_after) if closing_after is not None else None
    if now is None:
        now = _dates.now()
    kept = []
    for tender in tenders:
        if keyword and not matches_keyword(tender, keyword):
            continue
        if open_only and not tender.is_open(now):
            continue
        if before is not None or after is not None:
            if tender.deadline is None:
                continue
            if before is not None and tender.deadline >= before:
                continue
            if after is not None and tender.deadline < after:
                continue
        kept.append(tender)
    return kept


def sort_by_deadline(tenders: Iterable[Tender]) -> list[Tender]:
    """Sorts by deadline, earliest first. Tenders without a deadline come last, in their original order."""
    return sorted(tenders, key=lambda t: (t.deadline is None, t.deadline or _EARLIEST))
