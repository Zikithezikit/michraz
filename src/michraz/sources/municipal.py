"""Municipalities that run the shared bids page. Each one is a short subclass of :class:`BidsSource`."""

from __future__ import annotations

from michraz.sources.base import SourceName
from michraz.sources.bids import BidsSource


class AkkoSource(BidsSource):
    """Tenders of עיריית עכו."""

    name = SourceName.AKKO.value
    publisher = "עיריית עכו"
    domain = "www.akko.muni.il"
    path = "/he/bids/"


class AradSource(BidsSource):
    """Tenders of עיריית ערד."""

    name = SourceName.ARAD.value
    publisher = "עיריית ערד"
    domain = "www.arad.muni.il"


class BetShemeshSource(BidsSource):
    """Tenders of עיריית בית שמש."""

    name = SourceName.BETSHEMESH.value
    publisher = "עיריית בית שמש"
    domain = "www.betshemesh.muni.il"


class DimonaSource(BidsSource):
    """Tenders of עיריית דימונה."""

    name = SourceName.DIMONA.value
    publisher = "עיריית דימונה"
    domain = "www.dimona.muni.il"


class KfarSabaSource(BidsSource):
    """Tenders of עיריית כפר סבא."""

    name = SourceName.KFAR_SABA.value
    publisher = "עיריית כפר סבא"
    domain = "www.kfar-saba.muni.il"


class KiryatMotzkinSource(BidsSource):
    """Tenders of עיריית קריית מוצקין."""

    name = SourceName.KIRYAT_MOTZKIN.value
    publisher = "עיריית קריית מוצקין"
    domain = "www.kiryat-motzkin.muni.il"


class NesherSource(BidsSource):
    """Tenders of עיריית נשר."""

    name = SourceName.NESHER.value
    publisher = "עיריית נשר"
    domain = "www.nesher.muni.il"


class NetivotSource(BidsSource):
    """Tenders of עיריית נתיבות."""

    name = SourceName.NETIVOT.value
    publisher = "עיריית נתיבות"
    domain = "www.netivot.muni.il"


class NofHaGalilSource(BidsSource):
    """Tenders of עיריית נוף הגליל."""

    name = SourceName.NOF_HAGALIL.value
    publisher = "עיריית נוף הגליל"
    domain = "www.nof-hagalil.muni.il"


class SavyonSource(BidsSource):
    """Tenders of המועצה המקומית סביון."""

    name = SourceName.SAVYON.value
    publisher = "המועצה המקומית סביון"
    domain = "www.savyon.muni.il"


class TamraSource(BidsSource):
    """Tenders of עיריית טמרה."""

    name = SourceName.TAMRA.value
    publisher = "עיריית טמרה"
    domain = "www.tamra.muni.il"
    path = "/ar/bids/"


class YavneSource(BidsSource):
    """Tenders of עיריית יבנה."""

    name = SourceName.YAVNE.value
    publisher = "עיריית יבנה"
    domain = "www.yavne.muni.il"
