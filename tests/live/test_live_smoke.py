"""Hits each real service once and checks the response still has the shape the parsers expect.

Run by hand or from the manual ``live-smoke`` workflow: ``pytest -m live``. If one fails, a source changed. Record
a fresh fixture in a separate commit; never loosen the parser to hide it.
"""

import pytest

from michraz import BeerShevaSource, GovSource, RmiSource

pytestmark = pytest.mark.live


def test_rmi_search_shape():
    with RmiSource(cache_dir=None) as source:
        tenders = source.search()
    assert tenders, "RMI returned no open tenders"
    assert not source.errors
    first = tenders[0].extra["raw"]
    expected = {"MichrazID", "MichrazName", "KodYeshuv", "Shchuna", "PirsumDate", "PtichaDate", "SgiraDate"}
    assert expected <= set(first)
    assert all(t.deadline and t.deadline.tzinfo for t in tenders)


def test_rmi_server_side_settlement_filter_still_works():
    with RmiSource(cache_dir=None) as source:
        tenders = source.search(settlement_code=3750)
    assert tenders and {t.extra["settlement_code"] for t in tenders} == {3750}


def test_beersheva_shape():
    with BeerShevaSource(cache_dir=None, page_size=50) as source:
        tender = next(iter(source.fetch()))
    assert tender.title and tender.source_id and tender.url
    assert {"שם מכרז", "מספר מכרז", "תאריך אחרון להגשה", "זוכה במכרז", "קבצים", "URL"} <= set(tender.extra["raw"])


def test_gov_first_page_shape():
    with GovSource(cache_dir=None) as source:
        tender = next(iter(source.fetch()))
    assert tender.title and tender.source_id and tender.publisher
    assert tender.url.startswith("https://mr.gov.il/")
    assert not source.errors
