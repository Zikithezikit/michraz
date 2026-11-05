"""Central government tenders from the Government Procurement Administration portal (mr.gov.il).

The portal has no JSON API. Its search page is server-rendered HTML, so this source parses it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from html.parser import HTMLParser
from typing import Any

from michraz import _dates
from michraz._enums import StrEnum
from michraz.errors import SourceFormatError
from michraz.models import RAW_EXTRA_KEY, Tender
from michraz.sources.base import BaseSource, SourceName

SEARCH_URL = "https://mr.gov.il/ilgstorefront/he/search/"
TENDER_URL = "https://mr.gov.il/ilgstorefront/he/p/{}"
ATTRIBUTION = "Government Procurement Administration (מינהל הרכש הממשלתי), mr.gov.il"
DATE_FORMAT = "%d/%m/%Y"
DATETIME_FORMAT = "%d/%m/%Y %H:%M"
LABEL_SUFFIX = ":"
SEPARATOR = "|"

_RESULT_CLASS = "result-container"
_TITLE_CLASS = "search-results-content-head"
_TYPE_CLASS = "search-result-sub-head"
_TENDER_LINK = re.compile(r"^/ilgstorefront/he/p/(\d+)$")
_TOTAL = re.compile(r"נמצאו ([\d,]+) תוצאות")


class _Status(StrEnum):
    """Status facet values of the portal that mean a tender is still collecting offers."""

    PUBLISHED = "פורסם"
    UPDATED = "עודכן"
    NEW = "חדש"


class _Label(StrEnum):
    """Labels printed next to each value in a search result."""

    PUBLISHER = "שם המפרסם"
    PUBLICATION_NUMBER = "מס' פרסום"
    STATUS = "סטטוס"
    PROCEDURE_NUMBER = "מס׳ הליך"
    PUBLISHED = "תאריך פרסום"
    UPDATED = "תאריך עדכון"
    DEADLINE = "מועד אחרון להגשה"


class GovExtra(StrEnum):
    """Keys of ``Tender.extra`` for government tenders."""

    TYPE = "type"
    STATUS = "status"
    RAW = RAW_EXTRA_KEY


class _ResultParser(HTMLParser):
    """Splits a search page into one dict per result: ``id``, ``title``, ``type`` and the labelled values."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, Any]] = []
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._spans: list[str] = []

    def _current(self) -> dict[str, Any] | None:
        return self.results[-1] if self.results else None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "div" and _RESULT_CLASS in classes:
            self._finish()
            self.results.append({"id": None, "title": None, "type": None, "fields": {}})
        elif (result := self._current()) is None:
            return
        elif tag == "a" and result["id"] is None and (m := _TENDER_LINK.match(values.get("href") or "")):
            result["id"] = m.group(1)
        elif tag == "h2" and _TITLE_CLASS in classes:
            self._start("title")
        elif tag == "h3" and _TYPE_CLASS in classes:
            self._start("type")
        elif tag == "span":
            self._start("span")

    def _start(self, target: str) -> None:
        self._capture, self._buffer = target, []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture is None or tag not in {"h2", "h3", "span"}:
            return
        text = " ".join("".join(self._buffer).split())
        if self._capture == "span":
            if text:
                self._spans.append(text)
        elif (result := self._current()) is not None:
            result[self._capture] = text or None
        self._capture = None

    def _finish(self) -> None:
        result = self._current()
        if result is None:
            return
        spans, fields = self._spans, result["fields"]
        for position, text in enumerate(spans):
            following = spans[position + 1] if position + 1 < len(spans) else None
            if text.endswith(LABEL_SUFFIX) and following and not following.endswith(LABEL_SUFFIX):
                if following != SEPARATOR:
                    fields[text.removesuffix(LABEL_SUFFIX).strip()] = following
        self._spans = []

    def close(self) -> None:
        super().close()
        self._finish()


def parse_page(page: str) -> tuple[list[dict[str, Any]], int]:
    """Returns the results on one search page and the total result count the portal reports.

    Raises:
        ValueError: If the page has no result count, so it is not a search page.
    """
    match = _TOTAL.search(page)
    if match is None:
        raise ValueError("no result count on the page")
    parser = _ResultParser()
    parser.feed(page)
    parser.close()
    return parser.results, int(match.group(1).replace(",", ""))


class GovSource(BaseSource):
    """Tenders of ministries and other central-government bodies, from mr.gov.il.

    Only tenders whose portal status says they are still taking offers are read (published, updated, new).
    The portal returns 20 results per page, so a full read takes a few dozen requests. They are cached.

    Args:
        **settings: ``cache_dir``, ``cache_ttl`` and ``min_interval``, as for :class:`BaseSource`.
    """

    name = SourceName.GOV.value
    description = "Central government tenders (mr.gov.il)"
    attribution = ATTRIBUTION

    @staticmethod
    def _params(status: _Status, page: int) -> dict[str, Any]:
        return {"q": f":updateDate:archive:false:status:{status}", "text": "", "s": "TENDER", "page": page}

    def last_fetched(self) -> datetime | None:
        return None

    def fetch(self) -> Iterator[Tender]:
        """Yields every open tender, skipping records that fail to parse.

        Raises:
            SourceUnavailableError: If mr.gov.il cannot be reached.
            SourceFormatError: If a page is not a portal search page.
        """
        self.errors = []
        http = self._client()
        seen: set[str] = set()
        for status in _Status:
            page, read = 0, 0
            while True:
                text = http.get_text(self.name, SEARCH_URL, self._params(status, page))
                try:
                    results, total = parse_page(text)
                except ValueError as exc:
                    raise SourceFormatError(self.name, f"not a portal search page ({exc})") from exc
                for result in results:
                    try:
                        tender = self.parse(result)
                    except (KeyError, ValueError) as exc:
                        self._skip(result.get("id"), exc)
                        continue
                    if tender.source_id not in seen:
                        seen.add(tender.source_id)
                        yield tender
                read += len(results)
                page += 1
                if not results or read >= total:
                    break

    def parse(self, result: dict[str, Any]) -> Tender:
        """Converts one parsed search result to a :class:`Tender`.

        Raises:
            KeyError: If a required value is missing.
            ValueError: If a date does not match the portal format.
        """
        source_id, title = result["id"], result["title"]
        if not source_id or not title:
            raise KeyError("id or title")
        fields: dict[str, str] = result["fields"]
        return Tender(
            source=self.name,
            source_id=source_id,
            title=title,
            number=fields.get(_Label.PROCEDURE_NUMBER),
            publisher=fields.get(_Label.PUBLISHER),
            published_at=_dates.parse_local(fields.get(_Label.PUBLISHED), DATE_FORMAT),
            updated_at=_dates.parse_local(fields.get(_Label.UPDATED), DATE_FORMAT),
            deadline=_dates.parse_local(fields.get(_Label.DEADLINE), DATETIME_FORMAT),
            url=TENDER_URL.format(source_id),
            attribution=self.attribution,
            extra={GovExtra.TYPE: result["type"], GovExtra.STATUS: fields.get(_Label.STATUS), GovExtra.RAW: result},
        )
