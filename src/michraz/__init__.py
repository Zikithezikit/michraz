"""michraz: one clean interface to Israeli public tenders.

from michraz import Michraz

with Michraz() as m:
    for tender in m.search(keyword="גינון", open_only=True):
        print(tender.deadline, tender.title)
"""

from michraz._version import __version__
from michraz.client import Michraz
from michraz.errors import MichrazError, SourceFormatError, SourceUnavailableError
from michraz.export import to_csv, to_dataframe, to_dicts
from michraz.models import Document, Tender
from michraz.sources import BeerShevaExtra, BeerShevaSource, RmiExtra, RmiSource, Source, SourceName

__all__ = [
    "BeerShevaExtra",
    "BeerShevaSource",
    "Document",
    "Michraz",
    "MichrazError",
    "RmiExtra",
    "RmiSource",
    "Source",
    "SourceName",
    "SourceFormatError",
    "SourceUnavailableError",
    "Tender",
    "__version__",
    "to_csv",
    "to_dataframe",
    "to_dicts",
]
