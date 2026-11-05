"""Municipal tenders from the shared "bids" page that many Israeli municipal websites use.

Every site that runs the platform publishes its current tenders at ``https://www.<domain>/bids/`` as HTML tables.
The tables are laid out differently from city to city, so columns are found by their header text.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, time
from html.parser import HTMLParser
from typing import Any, ClassVar
from urllib.parse import parse_qs, urljoin, urlparse

from michraz import _dates
from michraz._enums import StrEnum
from michraz.errors import SourceFormatError
from michraz.models import RAW_EXTRA_KEY, Tender, TenderKind
from michraz.sources.base import BaseSource

BIDS_PATH = "/bids/"
DATE_FORMAT = "%d/%m/%Y"
ITEM_ID_PARAMETER = "id"
TABLE_CLASS = "bids"
_HIDDEN_CLASSES = frozenset({"only-in-mobile", "mobile-only", "sr-only"})
_VOID_TAGS = frozenset({"input", "br", "img", "hr", "meta", "link"})
_DATE = re.compile(r"\d{2}/\d{2}/\d{4}")
_PUBLISHED_HEADER = re.compile(r"(מועד|תאריך) (פרסום|פתיחת)|התחלת")
_DEADLINE_HEADER = re.compile(r"אחרון להגשה|סגירת")
_VACANCY_SECTION = re.compile(r"דרושים|כוח אדם|כח אדם|משאבי אנוש|מכרזי כ\"א")
_COMMITTEE = re.compile(r"^ועדת מכרזים")
_VACANCY_TITLE = re.compile(r"דרושים|דרוש/ה|מכרז (חיצוני|פנימי|פנים)")


class BidsExtra(StrEnum):
    """Keys of ``Tender.extra`` for tenders read from the bids page."""

    TYPE = "type"
    CATEGORY = "category"
    RAW = RAW_EXTRA_KEY


class _Header(StrEnum):
    """Header texts that name a column. Other headers are kept only in ``extra[RAW]``."""

    NAME = "שם המכרז"
    NUMBER = "מספר המכרז"
    TYPE = "סוג המכרז"
    CATEGORY = "קטגוריה"


@dataclass(slots=True)
class Table:
    """One bids table: its caption, its header texts and its rows."""

    caption: str
    headers: list[str]
    rows: list[list[Cell]]


@dataclass(slots=True)
class Cell:
    text: str = ""
    href: str | None = None


class _TableParser(HTMLParser):
    """Collects every ``<table class="bids">`` as a :class:`Table`."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[Table] = []
        self._caption = ""
        self._in_caption = False
        self._in_table = False
        self._headers: list[str] = []
        self._rows: list[list[Cell]] = []
        self._row: list[Cell] = []
        self._cell: Cell | None = None
        self._is_header = False
        self._hidden_tag: str | None = None
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if self._hidden_tag == tag:
            self._hidden_depth += 1
        elif self._hidden_tag is None and tag not in _VOID_TAGS and classes & _HIDDEN_CLASSES:
            self._hidden_tag, self._hidden_depth = tag, 1
        if tag == "table" and TABLE_CLASS in classes:
            self._in_table, self._headers, self._rows, self._caption = True, [], [], ""
        elif not self._in_table:
            return
        elif tag == "caption":
            self._in_caption = True
        elif tag == "tr":
            self._row = []
        elif tag in {"td", "th"}:
            self._cell, self._is_header = Cell(), tag == "th"
        elif tag == "a" and self._cell is not None and self._cell.href is None:
            self._cell.href = values.get("href")

    def handle_data(self, data: str) -> None:
        if self._in_caption:
            self._caption += data
        elif self._cell is not None and self._hidden_tag is None:
            self._cell.text += data

    def handle_endtag(self, tag: str) -> None:
        if self._hidden_tag == tag:
            self._hidden_depth -= 1
            if self._hidden_depth == 0:
                self._hidden_tag = None
        if not self._in_table:
            return
        if tag == "caption":
            self._in_caption = False
        elif tag in {"td", "th"} and self._cell is not None:
            self._cell.text = " ".join(self._cell.text.split())
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr":
            if self._is_header and not self._headers:
                self._headers = [cell.text for cell in self._row]
            elif self._row:
                self._rows.append(self._row)
            self._row, self._is_header = [], False
        elif tag == "table":
            self.tables.append(Table(" ".join(self._caption.split()), self._headers, self._rows))
            self._in_table = False


def parse_tables(page: str) -> list[Table]:
    """Returns every bids table on the page."""
    parser = _TableParser()
    parser.feed(page)
    parser.close()
    return parser.tables


def _column(headers: list[str], wanted: str | re.Pattern[str]) -> int | None:
    for index, header in enumerate(headers):
        matched = wanted.search(header) if isinstance(wanted, re.Pattern) else header == wanted
        if matched:
            return index
    return None


def _cell_text(row: list[Cell], index: int | None) -> str | None:
    if index is None or index >= len(row):
        return None
    return row[index].text or None


def _date(text: str | None, end_of_day: bool) -> datetime | None:
    match = _DATE.search(text or "")
    if match is None:
        return None
    moment = _dates.parse_local(match.group(), DATE_FORMAT)
    assert moment is not None
    return (
        datetime.combine(moment.date(), time.max.replace(microsecond=0), tzinfo=moment.tzinfo) if end_of_day else moment
    )


def _kind(caption: str, category: str | None, title: str) -> TenderKind:
    """Staff vacancies are recognized by the section they are listed in, or by wording in the title."""
    if _VACANCY_SECTION.search(caption) or _VACANCY_SECTION.search(category or "") or _VACANCY_TITLE.search(title):
        return TenderKind.VACANCY
    return TenderKind.TENDER


class BidsSource(BaseSource[tuple[Table, list[Cell]]]):
    """Base class for a municipality that runs the shared bids page.

    A subclass names the municipality and where its page lives, and nothing else::

        class KfarSabaSource(BidsSource):
            name = SourceName.KFAR_SABA
            publisher = "עיריית כפר סבא"
            domain = "www.kfar-saba.muni.il"

    ``description``, ``attribution`` and ``url`` are derived from these. A date-only deadline is read as the end
    of that day, because the page gives no hour. Staff vacancies that the site lists beside its tenders get
    ``kind=TenderKind.VACANCY``.

    Attributes:
        publisher: Name of the municipality in Hebrew.
        domain: Host of the municipal site.
        path: Path of the bids page. Some sites put a language in front of it.
        url: Full address of the bids page.
    """

    publisher: ClassVar[str]
    domain: ClassVar[str]
    path: ClassVar[str] = BIDS_PATH
    url: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "domain" in cls.__dict__:
            cls.description = f"{cls.publisher} tenders ({cls.domain})"
            cls.attribution = f"{cls.publisher}, {cls.domain}"
            cls.url = f"https://{cls.domain}{cls.path}"

    def __init__(self, **settings: Any) -> None:
        if not hasattr(type(self), "url"):
            raise TypeError("BidsSource is a base class: subclass it and set name, publisher and domain")
        super().__init__(**settings)

    def records(self) -> Iterator[tuple[Table, list[Cell]]]:
        """Yields ``(table, row)`` for every row of every table that has a tender name column.

        Rows about the tender committee itself (``ועדת מכרזים``, its meetings and protocols) are not tenders and
        are left out.

        Raises:
            SourceUnavailableError: If the site cannot be reached.
            SourceFormatError: If the page has no bids table.
        """
        tables = parse_tables(self._client().get_text(self.name, self.url))
        usable = [table for table in tables if _column(table.headers, _Header.NAME) is not None]
        if not usable:
            raise SourceFormatError(self.name, "no bids table with a tender name column on the page")
        for table in usable:
            name, category = _column(table.headers, _Header.NAME), _column(table.headers, _Header.CATEGORY)
            for row in table.rows:
                if not (
                    _COMMITTEE.search(_cell_text(row, name) or "") or _COMMITTEE.search(_cell_text(row, category) or "")
                ):
                    yield table, row

    def record_id(self, record: tuple[Table, list[Cell]]) -> object:
        _, row = record
        return row[0].text[:60] if row else None

    def parse(self, record: tuple[Table, list[Cell]]) -> Tender:
        """Converts one table row to a :class:`Tender`.

        Raises:
            ValueError: If the row has no title or no identifier.
        """
        table, row = record
        headers = table.headers
        title = _cell_text(row, _column(headers, _Header.NAME))
        if not title:
            raise ValueError("row has no title")
        number = _cell_text(row, _column(headers, _Header.NUMBER))
        link = next((cell.href for cell in row if cell.href), None)
        name_index = _column(headers, _Header.NAME)
        name_link = row[name_index].href if name_index is not None and name_index < len(row) else None
        href = name_link or link
        url = urljoin(f"https://{self.domain}/", href) if href else None
        ids = parse_qs(urlparse(url or "").query).get(ITEM_ID_PARAMETER)
        source_id = ids[0] if ids else number
        if not source_id:
            raise ValueError("row has neither an item id nor a tender number")
        raw = {header: cell.text for header, cell in zip(headers, row, strict=False)}
        return Tender(
            source=self.name,
            source_id=source_id,
            title=title,
            number=number,
            publisher=self.publisher,
            published_at=_date(_cell_text(row, _column(headers, _PUBLISHED_HEADER)), end_of_day=False),
            deadline=_date(_cell_text(row, _column(headers, _DEADLINE_HEADER)), end_of_day=True),
            url=url,
            kind=_kind(table.caption, _cell_text(row, _column(headers, _Header.CATEGORY)), title),
            attribution=self.attribution,
            extra={
                BidsExtra.TYPE: _cell_text(row, _column(headers, _Header.TYPE)),
                BidsExtra.CATEGORY: _cell_text(row, _column(headers, _Header.CATEGORY)),
                BidsExtra.RAW: raw,
            },
        )
