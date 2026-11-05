"""The source contract and a base class that handles HTTP plumbing and error collection."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from michraz._closeable import Closeable
from michraz._enums import StrEnum
from michraz._http import DEFAULT_CACHE_DIR, DEFAULT_CACHE_TTL, DEFAULT_MIN_INTERVAL, HttpClient
from michraz.models import Tender

logger = logging.getLogger(__name__)


class SourceName(StrEnum):
    """Names of the built-in sources, as they appear in ``Tender.source`` and ``--source``."""

    RMI = "rmi"
    BEERSHEVA = "beersheva"
    GOV = "gov"


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

    name: str
    description: str
    attribution: str
    errors: list[str]

    def fetch(self) -> Iterator[Tender]:
        """Yields every tender the source offers. A bad record is skipped and reported in ``errors``."""
        ...


class BaseSource(Closeable, ABC):
    """Shared plumbing for sources that read JSON over HTTP.

    A subclass sets ``name``, ``description`` and ``attribution`` and implements ``fetch``. Standalone use
    works without any setup: the source builds its own polite client on first use. Inside
    :class:`michraz.Michraz` the facade's client is shared instead.

    Args:
        cache_dir: Directory for cached responses. None disables the cache.
        cache_ttl: How long a cached response stays valid.
        min_interval: Minimum seconds between requests to the same host.
    """

    name: str
    description: str
    attribution: str

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
    def fetch(self) -> Iterator[Tender]:
        """Yields every tender the source offers. A bad record is skipped and reported in ``errors``."""

    def last_fetched(self) -> datetime | None:
        """Returns when this source last fetched data into the cache, or None if it never did."""
        return None

    def close(self) -> None:
        """Releases the connection pool if this source created it."""
        if self._owns_http and self._http is not None:
            self._http.close()
            self._http = None
            self._owns_http = False
