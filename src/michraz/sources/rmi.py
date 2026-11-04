"""Israel Land Authority (רשות מקרקעי ישראל) land tenders, from its public JSON API."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from functools import cache
from importlib import resources
from typing import Any

from michraz import _dates
from michraz._enums import StrEnum
from michraz._http import HttpMethod
from michraz.errors import SourceFormatError
from michraz.models import RAW_EXTRA_KEY, Tender
from michraz.sources.base import BaseSource, SourceName

API_BASE = "https://apps.land.gov.il/MichrazimSite/api"
SEARCH_URL = f"{API_BASE}/SearchApi/Search"
TENDER_URL = "https://apps.land.gov.il/MichrazimSite/#/michraz/{id}"
PUBLISHER = "רשות מקרקעי ישראל"
ATTRIBUTION = "Israel Land Authority (רשות מקרקעי ישראל), apps.land.gov.il"

SETTLEMENTS_PACKAGE = "michraz.sources"
SETTLEMENTS_FILE = "data/rmi_settlements.json"
SETTLEMENTS_KEY = "settlements"
TITLE_SEPARATOR = " - "


class RmiExtra(StrEnum):
    """Keys of ``Tender.extra`` for tenders from :class:`RmiSource`."""

    SETTLEMENT_CODE = "settlement_code"
    SETTLEMENT = "settlement"
    NEIGHBORHOOD = "neighborhood"
    REGION_CODE = "region_code"
    TYPE_CODE = "type_code"
    PURPOSE_CODE = "purpose_code"
    STATUS_CODE = "status_code"
    HOUSING_UNITS = "housing_units"
    COMMITTEE_AT = "committee_at"
    KHAL_YAAD_RASHI = "khal_yaad_rashi"
    MEKUVAN = "mekuvan"
    RAW = RAW_EXTRA_KEY


class _Request(StrEnum):
    """Keys of the search request body."""

    ACTIVE_QUICK_SEARCH = "ActiveQuickSearch"
    ACTIVE = "ActiveMichraz"
    SETTLEMENT = "KodYeshuv"
    NEIGHBORHOOD = "Shchuna"


class _Field(StrEnum):
    """Keys of one search result record."""

    ID = "MichrazID"
    NUMBER = "MichrazName"
    REGION = "KodMerchav"
    STATUS = "StatusMichraz"
    PURPOSE = "KodYeudMichraz"
    SETTLEMENT = "KodYeshuv"
    TYPE = "KodSugMichraz"
    MEKUVAN = "Mekuvan"
    HOUSING_UNITS = "YechidotDiur"
    NEIGHBORHOOD = "Shchuna"
    PUBLISHED = "PirsumDate"
    OPENS = "PtichaDate"
    DEADLINE = "SgiraDate"
    COMMITTEE = "VaadaDate"
    KHAL_YAAD_RASHI = "KhalYaadRashi"


@cache
def settlements() -> dict[int, str]:
    """Returns the settlement code table (``KodYeshuv`` to Hebrew name) shipped with the package."""
    text = resources.files(SETTLEMENTS_PACKAGE).joinpath(SETTLEMENTS_FILE).read_text(encoding="utf-8")
    return {int(code): name for code, name in json.loads(text)[SETTLEMENTS_KEY].items()}


def _title(settlement: str | None, neighborhood: str | None, number: str | None, source_id: str) -> str:
    parts = [part for part in (settlement, neighborhood) if part]
    return TITLE_SEPARATOR.join(parts) if parts else (number or source_id)


class RmiSource(BaseSource):
    """Open land tenders of the Israel Land Authority.

    The API returns every match in one response, so there is no paging. Only ``settlement_code`` and
    ``neighborhood`` are applied by the server. The other filters are applied here, after download, because
    the server was observed to ignore them (see ``docs/sources.md``).

    Region, tender type, purpose and status are exposed as the raw numeric codes the authority uses, under
    ``extra``. No official label table could be verified, so none is shipped. Use :class:`RmiExtra` for the
    keys of ``extra``.

    Args:
        **settings: ``cache_dir``, ``cache_ttl`` and ``min_interval``, as for :class:`BaseSource`.
    """

    name = SourceName.RMI.value
    description = "Israel Land Authority land tenders (apps.land.gov.il)"
    attribution = ATTRIBUTION

    @staticmethod
    def _body(active_only: bool, settlement_code: int | None, neighborhood: str | None) -> dict[str, Any]:
        body: dict[str, Any] = {_Request.ACTIVE_QUICK_SEARCH: False, _Request.ACTIVE: active_only}
        if settlement_code is not None:
            body[_Request.SETTLEMENT] = settlement_code
        if neighborhood:
            body[_Request.NEIGHBORHOOD] = neighborhood
        return body

    def last_fetched(self) -> datetime | None:
        return self._client().cached_at(HttpMethod.POST, SEARCH_URL, payload=self._body(True, None, None))

    def fetch(self) -> Iterator[Tender]:
        """Yields all currently open tenders. Same as ``iter(search())``."""
        return iter(self.search())

    def search(
        self,
        *,
        active_only: bool = True,
        settlement_code: int | None = None,
        neighborhood: str | None = None,
        tender_number: str | None = None,
        region: int | None = None,
        tender_type: int | None = None,
        purpose: int | None = None,
        status: int | None = None,
        raw_filters: dict[str, Any] | None = None,
    ) -> list[Tender]:
        """Searches RMI tenders.

        Args:
            active_only: Only tenders the authority lists as open. False asks for the whole archive
                (about 10 000 tenders), which is a large download.
            settlement_code: Settlement code (``KodYeshuv``), applied by the server.
            neighborhood: Neighborhood name, applied by the server.
            tender_number: Exact tender number such as ``"115/2017"``, applied after download.
            region: Region code, applied after download.
            tender_type: Tender type code, applied after download.
            purpose: Land-use purpose code, applied after download.
            status: Status code, applied after download.
            raw_filters: Extra keys merged into the request body as they are. Unstable: the server may
                ignore them, and they are not part of the supported API.

        Returns:
            Matching tenders in server order. Records that fail to parse are skipped and listed in
            ``errors``.

        Raises:
            SourceUnavailableError: If the service cannot be reached.
            SourceFormatError: If the response is not a list of records.
        """
        self.errors = []
        body = self._body(active_only, settlement_code, neighborhood)
        body.update(raw_filters or {})
        payload = self._client().post_json(self.name, SEARCH_URL, body)
        if not isinstance(payload, list):
            raise SourceFormatError(self.name, f"expected a JSON list, got: {str(payload)[:200]!r}")
        wanted = {
            _Field.NUMBER: tender_number,
            _Field.REGION: region,
            _Field.TYPE: tender_type,
            _Field.PURPOSE: purpose,
            _Field.STATUS: status,
        }
        tenders = []
        for record in payload:
            try:
                if any(v is not None and record.get(k) != v for k, v in wanted.items()):
                    continue
                tenders.append(self.parse(record))
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                self._skip(record.get(_Field.ID) if isinstance(record, dict) else None, exc)
        return tenders

    def parse(self, record: dict[str, Any]) -> Tender:
        """Converts one search result to a :class:`Tender`.

        Raises:
            KeyError: If ``MichrazID`` is missing.
            ValueError: If a date is not ISO 8601.
        """
        source_id = str(record[_Field.ID])
        number = (record.get(_Field.NUMBER) or "").strip() or None
        code = record.get(_Field.SETTLEMENT)
        settlement = settlements().get(code) if isinstance(code, int) else None
        neighborhood = (record.get(_Field.NEIGHBORHOOD) or "").strip() or None
        return Tender(
            source=self.name,
            source_id=source_id,
            title=_title(settlement, neighborhood, number, source_id),
            number=number,
            publisher=PUBLISHER,
            published_at=_dates.parse_iso(record.get(_Field.PUBLISHED)),
            opens_at=_dates.parse_iso(record.get(_Field.OPENS)),
            deadline=_dates.parse_iso(record.get(_Field.DEADLINE)),
            url=TENDER_URL.format(id=source_id),
            attribution=self.attribution,
            extra={
                RmiExtra.SETTLEMENT_CODE: code,
                RmiExtra.SETTLEMENT: settlement,
                RmiExtra.NEIGHBORHOOD: neighborhood,
                RmiExtra.REGION_CODE: record.get(_Field.REGION),
                RmiExtra.TYPE_CODE: record.get(_Field.TYPE),
                RmiExtra.PURPOSE_CODE: record.get(_Field.PURPOSE),
                RmiExtra.STATUS_CODE: record.get(_Field.STATUS),
                RmiExtra.HOUSING_UNITS: record.get(_Field.HOUSING_UNITS),
                RmiExtra.COMMITTEE_AT: _dates.parse_iso(record.get(_Field.COMMITTEE)),
                RmiExtra.KHAL_YAAD_RASHI: record.get(_Field.KHAL_YAAD_RASHI),
                RmiExtra.MEKUVAN: record.get(_Field.MEKUVAN),
                RmiExtra.RAW: record,
            },
        )
