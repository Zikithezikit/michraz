"""The source contract and a base class that handles HTTP plumbing and error collection."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from typing import ClassVar, Generic, Protocol, TypeVar, runtime_checkable

from michraz._closeable import Closeable
from michraz._enums import StrEnum
from michraz._http import DEFAULT_CACHE_DIR, DEFAULT_CACHE_TTL, DEFAULT_MIN_INTERVAL, HttpClient
from michraz.models import Tender

logger = logging.getLogger(__name__)

RecordT = TypeVar("RecordT")

PARSE_ERRORS = (KeyError, TypeError, ValueError, AttributeError)
"""What :meth:`BaseSource.parse` may raise for a record it cannot read. Such a record is skipped."""


class SourceName(StrEnum):
    """Names of the built-in sources, as they appear in ``Tender.source`` and ``--source``, in search order."""

    RMI = "rmi"
    BEERSHEVA = "beersheva"
    GOV = "gov"
    AKKO = "akko"
    ARAD = "arad"
    BETSHEMESH = "betshemesh"
    DIMONA = "dimona"
    KFAR_SABA = "kfar-saba"
    KIRYAT_MOTZKIN = "kiryat-motzkin"
    NESHER = "nesher"
    NETIVOT = "netivot"
    NOF_HAGALIL = "nof-hagalil"
    SAVYON = "savyon"
    TAMRA = "tamra"
    YAVNE = "yavne"


@runtime_checkable
class Source(Protocol):
    """Anything that can produce tenders.

    Adding a municipality means writing one class with these members, one fixture and one test.

    Attributes:
        name: Short unique identifier, such as ``"rmi"``.
        description: One line saying what the source covers.
        attribution: Credit line required by the data license.
        errors: Records skipped during the last :meth:`fetch`, one message each.
    """

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def attribution(self) -> str: ...

    errors: list[str]

    def fetch(self) -> Iterator[Tender]:
        """Yields every tender the source offers. A bad record is skipped and reported in ``errors``."""
        ...


class BaseSource(Closeable, ABC, Generic[RecordT]):
    """Template for a source: subclasses say how to read records and how to turn one into a tender.

    :meth:`fetch` is the same for every source. It reads :meth:`records`, converts each one with :meth:`parse`,
    skips and reports records that cannot be parsed, and drops repeated tenders. A subclass sets the class
    attributes ``name``, ``description`` and ``attribution`` and implements :meth:`records` and :meth:`parse`.
    Standalone use works without any setup: the source builds its own polite client on first use. Inside
    :class:`michraz.Michraz` the facade's client is shared instead.

    Args:
        cache_dir: Directory for cached responses. None disables the cache.
        cache_ttl: How long a cached response stays valid.
        min_interval: Minimum seconds between requests to the same host.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    attribution: ClassVar[str]

    def __init__(
        self,
        *,
        cache_dir: str | os.PathLike[str] | None = DEFAULT_CACHE_DIR,
        cache_ttl: timedelta = DEFAULT_CACHE_TTL,
        min_interval: float = DEFAULT_MIN_INTERVAL,
    ) -> None:
        self.errors: list[str] = []
        self._cache_dir = cache_dir
        self._cache_ttl = cache_ttl
        self._min_interval = min_interval
        self._http: HttpClient | None = None
        self._owns_http = False

    def bind(self, http: HttpClient) -> None:
        """Shares a client with this source unless it already built its own."""
        if self._http is None:
            self._http = http

    def _client(self) -> HttpClient:
        if self._http is None:
            self._http = HttpClient(
                cache_dir=self._cache_dir, cache_ttl=self._cache_ttl, min_interval=self._min_interval
            )
            self._owns_http = True
        return self._http

    def _skip(self, record_id: object, exc: Exception) -> None:
        message = f"{self.name}: skipped record {record_id!r}: {exc!r}"
        self.errors.append(message)
        logger.warning(message)

    @abstractmethod
    def records(self) -> Iterator[RecordT]:
        """Reads the upstream data and yields its records one by one.

        Raises:
            SourceUnavailableError: If the service cannot be reached.
            SourceFormatError: If the response does not have the expected shape.
        """

    @abstractmethod
    def parse(self, record: RecordT) -> Tender:
        """Converts one record to a :class:`Tender`. May raise any of :data:`PARSE_ERRORS`."""

    def record_id(self, record: RecordT) -> object:
        """Identifies a record in the message reported when it is skipped."""
        return None

    def fetch(self) -> Iterator[Tender]:
        """Yields every tender the source offers. A bad record is skipped and reported in ``errors``."""
        return self._tenders(self.records())

    def _tenders(self, records: Iterable[RecordT]) -> Iterator[Tender]:
        self.errors = []
        seen: set[tuple[str, str]] = set()
        for record in records:
            try:
                tender = self.parse(record)
            except PARSE_ERRORS as exc:
                self._skip(self.record_id(record), exc)
                continue
            if tender.key not in seen:
                seen.add(tender.key)
                yield tender

    def last_fetched(self) -> datetime | None:
        """Returns when this source last fetched data into the cache, or None if it never did."""
        return None

    def close(self) -> None:
        """Releases the connection pool if this source created it."""
        if self._owns_http and self._http is not None:
            self._http.close()
            self._http = None
            self._owns_http = False
