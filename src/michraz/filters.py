"""Client-side filtering and sorting of tenders."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
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


def _bound(value: datetime | date | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime bounds must be timezone-aware")
        return value
    return datetime.combine(value, time.min, tzinfo=_dates.JERUSALEM)


@dataclass(frozen=True, slots=True, kw_only=True)
class TenderFilter:
    """A set of conditions a tender must meet. Every given condition must hold.

    Attributes:
        keyword: Keep tenders whose title or number contains this text.
        open_only: Keep tenders for which :meth:`Tender.is_open` is true.
        closing_before: Keep tenders whose deadline is strictly before this moment. A plain date means
            00:00 at the start of that day in Asia/Jerusalem.
        closing_after: Keep tenders whose deadline is at or after this moment. Dates are read as above.
        now: Moment used for ``open_only``. Defaults to the current time on each call.

    Raises:
        ValueError: If a datetime bound or ``now`` is naive.
    """

    keyword: str | None = None
    open_only: bool = False
    closing_before: datetime | date | None = None
    closing_after: datetime | date | None = None
    now: datetime | None = None

    def __post_init__(self) -> None:
        _bound(self.closing_before)
        _bound(self.closing_after)
        if self.now is not None and self.now.tzinfo is None:
            raise ValueError("now must be timezone-aware")

    def matches(self, tender: Tender) -> bool:
        """Tells whether ``tender`` meets every condition."""
        if self.keyword and not matches_keyword(tender, self.keyword):
            return False
        if self.open_only and not tender.is_open(self.now):
            return False
        before = _bound(self.closing_before)
        after = _bound(self.closing_after)
        if before is None and after is None:
            return True
        if tender.deadline is None:
            return False
        return (before is None or tender.deadline < before) and (after is None or tender.deadline >= after)

    def apply(self, tenders: Iterable[Tender]) -> list[Tender]:
        """Returns the matching tenders in their original order.

        Tenders without a deadline never match a closing bound.
        """
        return [tender for tender in tenders if self.matches(tender)]


def apply_filters(
    tenders: Iterable[Tender],
    *,
    keyword: str | None = None,
    open_only: bool = False,
    closing_before: datetime | date | None = None,
    closing_after: datetime | date | None = None,
    now: datetime | None = None,
) -> list[Tender]:
    """Filters tenders. Shorthand for ``TenderFilter(...).apply(tenders)``; see :class:`TenderFilter`."""
    return TenderFilter(
        keyword=keyword, open_only=open_only, closing_before=closing_before, closing_after=closing_after, now=now
    ).apply(tenders)


def sort_by_deadline(tenders: Iterable[Tender]) -> list[Tender]:
    """Sorts by deadline, earliest first. Tenders without a deadline come last, in their original order."""
    return sorted(tenders, key=lambda t: (t.deadline is None, t.deadline or _EARLIEST))
