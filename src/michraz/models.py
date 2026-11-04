"""The normalized tender model shared by every source."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from michraz import _dates


@dataclass(frozen=True, slots=True)
class Document:
    """A file attached to a tender.

    Attributes:
        title: Link text as the publisher wrote it.
        url: Absolute URL of the file.
    """

    title: str
    url: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Tender:
    """One public tender, normalized across sources.

    Hebrew text is kept verbatim apart from trimmed whitespace. Every datetime is timezone-aware. Two tenders
    are equal when all fields except ``extra`` are equal.

    Attributes:
        source: Name of the source that produced the tender, ``"rmi"`` or ``"beersheva"``.
        source_id: Identifier that is unique and stable within the source.
        title: Human-readable title.
        number: Tender number as published, for example ``"33/2026"``.
        publisher: Name of the publishing body, in Hebrew.
        published_at: When the tender was published.
        opens_at: When submissions open.
        deadline: Submission deadline.
        updated_at: When the publisher last updated the tender.
        winner: Name of the winner. None while the tender is still open.
        url: Page of the tender on the publisher's site.
        documents: Attached files.
        attribution: Credit line required by the data license. Always keep it with the data.
        extra: Source-specific fields. The untouched record is under ``extra["raw"]``.
    """

    source: str
    source_id: str
    title: str
    attribution: str
    number: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    opens_at: datetime | None = None
    deadline: datetime | None = None
    updated_at: datetime | None = None
    winner: str | None = None
    url: str | None = None
    documents: tuple[Document, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict, compare=False, hash=False, repr=False)

    @property
    def key(self) -> tuple[str, str]:
        """``(source, source_id)``, unique across sources."""
        return (self.source, self.source_id)

    def is_open(self, now: datetime | None = None) -> bool:
        """Tells whether the tender can still receive submissions.

        A tender is open when it has no winner and its deadline is strictly in the future. A tender without
        a known deadline is treated as closed.

        Args:
            now: Moment to compare against. Defaults to the current time.

        Returns:
            True if the tender is open at ``now``.

        Raises:
            ValueError: If ``now`` is a naive datetime.
        """
        if now is None:
            now = _dates.now()
        elif now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return self.winner is None and self.deadline is not None and self.deadline > now
