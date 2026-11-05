"""The :class:`Michraz` facade: one object to search every source."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from datetime import date, datetime, timedelta

from michraz._closeable import Closeable
from michraz._http import (
    DEFAULT_CACHE_DIR,
    DEFAULT_CACHE_TTL,
    DEFAULT_MIN_INTERVAL,
    HttpClient,
)
from michraz.errors import MichrazError
from michraz.filters import TenderFilter, sort_by_deadline
from michraz.models import Tender, TenderKind
from michraz.sources import BaseSource, BeerShevaSource, GovSource, RmiSource, Source, municipal_sources

logger = logging.getLogger(__name__)


def _default_sources() -> tuple[Source, ...]:
    return (RmiSource(), BeerShevaSource(), GovSource(), *municipal_sources())


class Michraz(Closeable):
    """Searches several tender sources through one polite HTTP client.

    Use it as a context manager so the connection pool is closed:

        with Michraz() as m:
            tenders = m.search(keyword="גינון", open_only=True)

    Args:
        sources: Sources to search. Defaults to RMI, Beer Sheva, the central government and the municipalities in
            :data:`michraz.sources.bids.MUNICIPALITIES`.
        cache_dir: Directory for cached responses. Defaults to ``~/.cache/michraz``. None disables the cache.
        cache_ttl: How long a cached response stays valid.
        min_interval: Minimum seconds between requests to the same host. Must be at least 0.5.

    Attributes:
        sources: The sources in use.
        last_errors: Records skipped during the last :meth:`search`, one message each.

    Raises:
        ValueError: If ``min_interval`` is below 0.5 seconds or two sources share a name.
    """

    def __init__(
        self,
        sources: Sequence[Source] | None = None,
        cache_dir: str | os.PathLike[str] | None = DEFAULT_CACHE_DIR,
        cache_ttl: timedelta = DEFAULT_CACHE_TTL,
        min_interval: float = DEFAULT_MIN_INTERVAL,
    ) -> None:
        self._http = HttpClient(cache_dir=cache_dir, cache_ttl=cache_ttl, min_interval=min_interval)
        self.sources: tuple[Source, ...] = (
            tuple(sources)
            if sources is not None
            else (RmiSource(), BeerShevaSource(), GovSource(), *municipal_sources())
        )
        names = [s.name for s in self.sources]
        if len(set(names)) != len(names):
            raise ValueError(f"source names must be unique, got {names}")
        for source in self.sources:
            if isinstance(source, BaseSource):
                source.bind(self._http)
        self.last_errors: list[str] = []

    def search(
        self,
        keyword: str | None = None,
        open_only: bool = False,
        source: str | None = None,
        closing_before: datetime | date | None = None,
        closing_after: datetime | date | None = None,
        kind: TenderKind | None = TenderKind.TENDER,
    ) -> list[Tender]:
        """Fetches tenders from the sources and filters them.

        Args:
            keyword: Keep tenders whose title or number contains this text (case-insensitive, NFKC).
            open_only: Keep only tenders that can still receive submissions.
            source: Search only the source with this name.
            closing_before: Keep tenders whose deadline is before this moment. A date means the start of
                that day in Asia/Jerusalem.
            closing_after: Keep tenders whose deadline is at or after this moment.
            kind: Keep only this kind of listing. Defaults to tenders, which hides the staff vacancies that some
                municipal sites list next to them. Pass ``TenderKind.VACANCY`` for only those, or None for both.

        Returns:
            Matching tenders sorted by deadline, earliest first. Tenders without a deadline come last.

        Raises:
            ValueError: If ``source`` names no known source or a datetime bound is naive.
            SourceUnavailableError: If every searched source cannot be reached.
            SourceFormatError: If every searched source answers in an unexpected shape. When only some
                sources fail, their errors are listed in :attr:`last_errors` and the rest are returned.
        """
        criteria = TenderFilter(
            keyword=keyword,
            open_only=open_only,
            closing_before=closing_before,
            closing_after=closing_after,
            kind=kind,
        )
        self.last_errors = []
        tenders: list[Tender] = []
        chosen = self._select(source)
        failures: list[MichrazError] = []
        for src in chosen:
            try:
                tenders.extend(list(src.fetch()))
            except MichrazError as exc:
                logger.warning("%s failed: %s", src.name, exc)
                failures.append(exc)
                self.last_errors.append(str(exc))
                continue
            self.last_errors.extend(src.errors)
        if failures and len(failures) == len(chosen):
            raise failures[0]
        return sort_by_deadline(criteria.apply(tenders))

    def _select(self, name: str | None) -> tuple[Source, ...]:
        if name is None:
            return self.sources
        chosen = tuple(s for s in self.sources if s.name == name)
        if not chosen:
            known = ", ".join(s.name for s in self.sources)
            raise ValueError(f"unknown source {name!r}; known sources: {known}")
        return chosen

    def __repr__(self) -> str:
        return f"{type(self).__name__}(sources={[s.name for s in self.sources]})"

    def close(self) -> None:
        """Closes the shared connection pool."""
        self._http.close()
        for source in self.sources:
            if isinstance(source, BaseSource):
                source.close()
