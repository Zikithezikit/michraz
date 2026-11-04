"""Query one source directly, with its own filters.

RMI applies settlement and neighborhood on the server. Tender number, region, type, purpose and status are
applied after download. Codes are the raw numbers the Israel Land Authority uses.
"""

from michraz import RmiExtra, RmiSource

with RmiSource() as rmi:
    tenders = rmi.search(settlement_code=3750)  # 3750 is Alfei Menashe
    for tender in tenders:
        print(tender.number, tender.title, tender.deadline)
        print(
            "   housing units:",
            tender.extra[RmiExtra.HOUSING_UNITS],
            "| region code:",
            tender.extra[RmiExtra.REGION_CODE],
        )
