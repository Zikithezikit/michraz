"""Israel Land Authority (רשות מקרקעי ישראל) land tenders, from its public JSON API."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from functools import cache
from importlib import resources
from typing import Any

from michraz import _dates
from michraz.errors import SourceFormatError
from michraz.models import Tender
from michraz.sources.base import BaseSource

API_BASE = "https://apps.land.gov.il/MichrazimSite/api"
SEARCH_URL = f"{API_BASE}/SearchApi/Search"
TENDER_URL = "https://apps.land.gov.il/MichrazimSite/#/michraz/{id}"
PUBLISHER = "רשות מקרקעי ישראל"
ATTRIBUTION = "Israel Land Authority (רשות מקרקעי ישראל), apps.land.gov.il"


@cache
def settlements() -> dict[int, str]:
    """Returns the settlement code table (``KodYeshuv`` to Hebrew name) shipped with the package."""
    text = resources.files("michraz.sources").joinpath("data/rmi_settlements.json").read_text(encoding="utf-8")
    return {int(code): name for code, name in json.loads(text)["settlements"].items()}


def _title(settlement: str | None, neighborhood: str | None, number: str | None, source_id: str) -> str:
    parts = [part for part in (settlement, neighborhood) if part]
    return " - ".join(parts) if parts else (number or source_id)


class RmiSource(BaseSource):
    """Open land tenders of the Israel Land Authority.

    The API returns every match in one response, so there is no paging. Only ``settlement_code`` and
    ``neighborhood`` are applied by the server. The other filters are applied here, after download, because
    the server was observed to ignore them (see ``docs/sources.md``).

    Region, tender type, purpose and status are exposed as the raw numeric codes the authority uses, under
    ``extra``. No official label table could be verified, so none is shipped.

    Args:
        **settings: ``cache_dir``, ``cache_ttl`` and ``min_interval``, as for :class:`BaseSource`.
    """

    name = "rmi"
    description = "Israel Land Authority land tenders (apps.land.gov.il)"
    attribution = ATTRIBUTION

    @staticmethod
    def _body(active_only: bool, settlement_code: int | None, neighborhood: str | None) -> dict[str, Any]:
        body: dict[str, Any] = {"ActiveQuickSearch": False, "ActiveMichraz": active_only}
        if settlement_code is not None:
            body["KodYeshuv"] = settlement_code
        if neighborhood:
            body["Shchuna"] = neighborhood
        return body

    def last_fetched(self) -> datetime | None:
        return self._client().cached_at("POST", SEARCH_URL, payload=self._body(True, None, None))

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
            "MichrazName": tender_number,
            "KodMerchav": region,
            "KodSugMichraz": tender_type,
            "KodYeudMichraz": purpose,
            "StatusMichraz": status,
        }
        tenders = []
        for record in payload:
            try:
                if any(v is not None and record.get(k) != v for k, v in wanted.items()):
                    continue
                tenders.append(self.parse(record))
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                self._skip(record.get("MichrazID") if isinstance(record, dict) else None, exc)
        return tenders

    def parse(self, record: dict[str, Any]) -> Tender:
        """Converts one search result to a :class:`Tender`.

        Raises:
            KeyError: If ``MichrazID`` is missing.
            ValueError: If a date is not ISO 8601.
        """
        source_id = str(record["MichrazID"])
        number = (record.get("MichrazName") or "").strip() or None
        code = record.get("KodYeshuv")
        settlement = settlements().get(code) if isinstance(code, int) else None
        neighborhood = (record.get("Shchuna") or "").strip() or None
        return Tender(
            source=self.name,
            source_id=source_id,
            title=_title(settlement, neighborhood, number, source_id),
            number=number,
            publisher=PUBLISHER,
            published_at=_dates.parse_iso(record.get("PirsumDate")),
            opens_at=_dates.parse_iso(record.get("PtichaDate")),
            deadline=_dates.parse_iso(record.get("SgiraDate")),
            url=TENDER_URL.format(id=source_id),
            attribution=self.attribution,
            extra={
                "settlement_code": code,
                "settlement": settlement,
                "neighborhood": neighborhood,
                "region_code": record.get("KodMerchav"),
                "type_code": record.get("KodSugMichraz"),
                "purpose_code": record.get("KodYeudMichraz"),
                "status_code": record.get("StatusMichraz"),
                "housing_units": record.get("YechidotDiur"),
                "khal_yaad_rashi": record.get("KhalYaadRashi"),
                "committee_at": _dates.parse_iso(record.get("VaadaDate")),
                "mekuvan": record.get("Mekuvan"),
                "raw": record,
            },
        )
