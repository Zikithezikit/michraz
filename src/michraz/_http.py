"""Polite HTTP client shared by every source.

Government services are not built for heavy traffic, so this client sends an honest User-Agent, waits between
requests to the same host, caches successful responses on disk and backs off when a server asks it to.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import TracebackType
from typing import Any

import httpx

from michraz._version import __version__
from michraz.errors import SourceFormatError, SourceUnavailableError

logger = logging.getLogger(__name__)

USER_AGENT = f"michraz/{__version__} (+https://github.com/Zikithezikit/michraz)"
DEFAULT_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "michraz"
DEFAULT_CACHE_TTL = timedelta(hours=1)
DEFAULT_MIN_INTERVAL = 1.0
MIN_INTERVAL_FLOOR = 0.5
MAX_RETRIES = 2
BACKOFF_BASE = 1.0
MAX_RETRY_AFTER = 60.0
TIMEOUT = httpx.Timeout(30.0, connect=10.0)
SAMPLE_CHARS = 200


def _truncate(text: str) -> str:
    return text if len(text) <= SAMPLE_CHARS else text[:SAMPLE_CHARS] + "..."


def _retry_after(header: str | None, wall_clock: Callable[[], float]) -> float | None:
    """Parses a Retry-After header given in seconds or as an HTTP date."""
    if not header:
        return None
    try:
        return max(0.0, float(header))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, when.timestamp() - wall_clock())


class _DiskCache:
    """JSON files on disk, one per request, valid for ``ttl``."""

    def __init__(self, directory: Path, ttl: timedelta, wall_clock: Callable[[], float]) -> None:
        self.directory = directory
        self.ttl = ttl
        self._wall_clock = wall_clock

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def read(self, key: str) -> tuple[float, Any] | None:
        """Returns ``(fetched_at, data)`` regardless of age, or None if absent or unreadable."""
        try:
            entry = json.loads(self._path(key).read_text(encoding="utf-8"))
            return float(entry["fetched_at"]), entry["data"]
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def fresh(self, key: str) -> tuple[float, Any] | None:
        entry = self.read(key)
        if entry is None or self._wall_clock() - entry[0] >= self.ttl.total_seconds():
            return None
        return entry

    def write(self, key: str, data: Any) -> None:
        payload = json.dumps({"fetched_at": self._wall_clock(), "data": data}, ensure_ascii=False)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.directory, suffix=".tmp", delete=False
            ) as handle:
                handle.write(payload)
            os.replace(handle.name, self._path(key))
        except OSError as exc:  # a cache that cannot be written must never break a search
            logger.debug("could not write cache entry: %s", exc)


def _request_key(method: str, url: str, payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False) if payload is not None else ""
    return hashlib.sha256(f"{method}\n{url}\n{body}".encode()).hexdigest()


class HttpClient:
    """Rate-limited, caching JSON client with bounded retries.

    Args:
        cache_dir: Directory for cached responses. None disables the cache.
        cache_ttl: How long a cached response stays valid.
        min_interval: Minimum seconds between requests to the same host. Must be at least 0.5.
        client: An ``httpx.Client`` to use. By default one is created and owned by this object.
        clock: Monotonic clock in seconds. Replace it in tests.
        sleep: Sleep function. Replace it in tests so they do not wait.
        wall_clock: Wall-clock time in seconds since the epoch, used for cache age.

    Raises:
        ValueError: If ``min_interval`` is below 0.5 seconds.
    """

    def __init__(
        self,
        *,
        cache_dir: str | os.PathLike[str] | None = DEFAULT_CACHE_DIR,
        cache_ttl: timedelta = DEFAULT_CACHE_TTL,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        if min_interval < MIN_INTERVAL_FLOOR:
            raise ValueError(f"min_interval must be at least {MIN_INTERVAL_FLOOR} seconds")
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._wall_clock = wall_clock
        self._owns_client = client is None
        self._client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=TIMEOUT
        )
        self._cache = _DiskCache(Path(cache_dir).expanduser(), cache_ttl, wall_clock) if cache_dir else None
        self._last_request: dict[str, float] = {}

    def close(self) -> None:
        """Closes the underlying connection pool if this object created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()

    def get_json(self, source: str, url: str, params: Mapping[str, Any] | None = None) -> Any:
        """Fetches ``url`` with GET and returns the decoded JSON body.

        Args:
            source: Name of the calling source, used in error messages.
            url: Absolute URL.
            params: Query parameters.

        Raises:
            SourceUnavailableError: If the host cannot be reached or answers with an error status.
            SourceFormatError: If the body is not JSON.
        """
        return self._json(source, "GET", self._full_url(url, params), None)

    def post_json(self, source: str, url: str, payload: Any) -> Any:
        """Sends ``payload`` as JSON with POST and returns the decoded JSON body.

        Raises:
            SourceUnavailableError: If the host cannot be reached or answers with an error status.
            SourceFormatError: If the body is not JSON.
        """
        return self._json(source, "POST", url, payload)

    def cached_at(
        self, method: str, url: str, params: Mapping[str, Any] | None = None, payload: Any = None
    ) -> datetime | None:
        """Returns when a request was last fetched into the cache, even if the entry has expired."""
        if self._cache is None:
            return None
        entry = self._cache.read(_request_key(method, self._full_url(url, params), payload))
        return datetime.fromtimestamp(entry[0], tz=timezone.utc) if entry else None

    @staticmethod
    def _full_url(url: str, params: Mapping[str, Any] | None) -> str:
        return str(httpx.URL(url, params=params)) if params else url

    def _json(self, source: str, method: str, url: str, payload: Any) -> Any:
        key = _request_key(method, url, payload)
        if self._cache and (hit := self._cache.fresh(key)) is not None:
            logger.debug("cache hit for %s", url)
            return hit[1]
        response = self._send(source, method, url, payload)
        try:
            data = response.json()
        except ValueError as exc:
            raise SourceFormatError(source, f"response is not JSON: {_truncate(response.text)!r}") from exc
        if self._cache:
            self._cache.write(key, data)
        return data

    def _throttle(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = last + self.min_interval - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last_request[host] = self._clock()

    def _send(self, source: str, method: str, url: str, payload: Any) -> httpx.Response:
        host = httpx.URL(url).host
        for attempt in range(MAX_RETRIES + 1):
            self._throttle(host)
            try:
                response = self._client.request(method, url, json=payload)
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(source, f"request to {host} failed: {exc}") from exc
            status = response.status_code
            retryable = status == 429 or status >= 500
            if not retryable or attempt == MAX_RETRIES:
                break
            delay = _retry_after(response.headers.get("Retry-After"), self._wall_clock)
            if delay is None:
                delay = BACKOFF_BASE * 2**attempt
            if delay > MAX_RETRY_AFTER:
                raise SourceUnavailableError(source, f"{host} asked to wait {delay:.0f}s (HTTP {status}); giving up")
            logger.warning("%s answered HTTP %d, retrying in %.1fs", host, status, delay)
            self._sleep(delay)
        if status >= 300:
            raise SourceUnavailableError(source, f"HTTP {status} from {url}")
        return response
