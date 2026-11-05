"""Beer Sheva municipal tenders, published as a CKAN datastore on data.gov.il."""

from __future__ import annotations

import html
from collections.abc import Iterator
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlparse

from michraz import _dates
from michraz._enums import StrEnum
from michraz._http import HttpMethod
from michraz.errors import SourceFormatError
from michraz.models import RAW_EXTRA_KEY, Document, Tender
from michraz.sources.base import BaseSource, SourceName

API_URL = "https://data.gov.il/api/3/action/datastore_search"
RESOURCE_ID = "6a281768-6327-420b-a1c5-fb84af1fa8ae"
PUBLISHER = "עיריית באר שבע"
ATTRIBUTION = "Beer Sheva Municipality (עיריית באר שבע), via data.gov.il, license: Other (Open)"
DEFAULT_PAGE_SIZE = 1000


class _Column(StrEnum):
    """Column names of the datastore, as the municipality publishes them."""

    TITLE = "שם מכרז"
    NUMBER = "מספר מכרז"
    DEADLINE = "תאריך אחרון להגשה"
    UPDATED = "תאריך עדכון"
    WINNER = "זוכה במכרז"
    FILES = "קבצים"
    PAYMENT = "תשלום מקוון"
    URL = "URL"
    ROW_ID = "_id"


class _Ckan(StrEnum):
    """Keys of the CKAN datastore API."""

    SUCCESS = "success"
    RESULT = "result"
    RECORDS = "records"
    TOTAL = "total"
    RESOURCE_ID = "resource_id"
    LIMIT = "limit"
    OFFSET = "offset"


class BeerShevaExtra(StrEnum):
    """Keys of ``Tender.extra`` for tenders from :class:`BeerShevaSource`."""

    PAYMENT_URL = "payment_url"
    RAW = RAW_EXTRA_KEY


ITEM_ID_PARAMETER = "ID"
LINK_TAG = "a"
LINK_HREF = "href"


class _LinkParser(HTMLParser):
    """Collects ``(text, href)`` for every anchor in an HTML fragment."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == LINK_TAG:
            self._href = dict(attrs).get(LINK_HREF) or ""
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == LINK_TAG and self._href is not None:
            self.links.append((" ".join("".join(self._text).split()), self._href.strip()))
            self._href = None


def parse_documents(fragment: str | None) -> tuple[Document, ...]:
    """Extracts the attached files from the ``קבצים`` column, which holds raw HTML."""
    if not fragment or not fragment.strip():
        return ()
    parser = _LinkParser()
    parser.feed(fragment)
    parser.close()
    return tuple(Document(title=text or href, url=href) for text, href in parser.links if href)


def _text(value: Any) -> str | None:
    """Unescapes HTML entities and trims; blank becomes None."""
    if value is None:
        return None
    cleaned = html.unescape(str(value)).strip()
    return cleaned or None


def _item_id(url: str | None) -> str | None:
    """The municipality's list-item id from ``...DispForm.aspx?ID=896``."""
    if not url:
        return None
    ids = parse_qs(urlparse(url).query).get(ITEM_ID_PARAMETER)
    return ids[0] if ids else None


class BeerShevaSource(BaseSource[dict[str, Any]]):
    """Tenders of the Beer Sheva municipality (dataset ``tender-br7``, refreshed weekly).

    ``source_id`` is the municipality's own list-item id taken from the tender page URL. The tender number is
    not a usable key: some rows have none and a few numbers repeat.

    Args:
        page_size: Rows requested per call. The dataset is read page by page until ``total`` is reached.
        **settings: ``cache_dir``, ``cache_ttl`` and ``min_interval``, as for :class:`BaseSource`.
    """

    name = SourceName.BEERSHEVA.value
    description = "Beer Sheva municipal tenders (data.gov.il, weekly)"
    attribution = ATTRIBUTION

    def __init__(self, *, page_size: int = DEFAULT_PAGE_SIZE, **settings: Any) -> None:
        super().__init__(**settings)
        if page_size < 1:
            raise ValueError("page_size must be at least 1")
        self.page_size = page_size

    def _params(self, offset: int) -> dict[str, Any]:
        return {_Ckan.RESOURCE_ID: RESOURCE_ID, _Ckan.LIMIT: self.page_size, _Ckan.OFFSET: offset}

    def last_fetched(self) -> datetime | None:
        return self._client().cached_at(HttpMethod.GET, API_URL, self._params(0))

    def records(self) -> Iterator[dict[str, Any]]:
        """Yields every row of the dataset, page by page.

        Raises:
            SourceUnavailableError: If data.gov.il cannot be reached.
            SourceFormatError: If a page is not a CKAN datastore response.
        """
        http = self._client()
        offset = 0
        while True:
            payload = http.get_json(self.name, API_URL, self._params(offset))
            records, total = self._unwrap(payload)
            yield from records
            offset += len(records)
            if not records or offset >= total:
                return

    def record_id(self, record: dict[str, Any]) -> object:
        return record.get(_Column.ROW_ID) if isinstance(record, dict) else None

    def _unwrap(self, payload: Any) -> tuple[list[Any], int]:
        try:
            if payload[_Ckan.SUCCESS] is not True:
                raise ValueError("success is not true")
            result = payload[_Ckan.RESULT]
            records, total = result[_Ckan.RECORDS], result[_Ckan.TOTAL]
            if not isinstance(records, list) or not isinstance(total, int):
                raise ValueError("records or total has the wrong type")
        except (KeyError, TypeError, ValueError) as exc:
            sample = str(payload)[:200]
            raise SourceFormatError(self.name, f"not a CKAN datastore response ({exc}): {sample!r}") from exc
        return records, total

    def parse(self, record: dict[str, Any]) -> Tender:
        """Converts one datastore row to a :class:`Tender`.

        Raises:
            KeyError: If a column is missing.
            ValueError: If a date does not match ``dd/mm/yyyy HH:MM:SS`` or the row has no identifier.
        """
        url = _text(record[_Column.URL])
        number = _text(record[_Column.NUMBER])
        source_id = _item_id(url) or number
        if source_id is None:
            raise ValueError("row has neither a list-item id nor a tender number")
        title = _text(record[_Column.TITLE])
        if title is None:
            raise ValueError("row has no title")
        return Tender(
            source=self.name,
            source_id=source_id,
            title=title,
            number=number,
            publisher=PUBLISHER,
            deadline=_dates.parse_local(record[_Column.DEADLINE]),
            updated_at=_dates.parse_local(record[_Column.UPDATED]),
            winner=_text(record[_Column.WINNER]),
            url=url,
            documents=parse_documents(record[_Column.FILES]),
            attribution=self.attribution,
            extra={BeerShevaExtra.PAYMENT_URL: _text(record.get(_Column.PAYMENT)), BeerShevaExtra.RAW: record},
        )
