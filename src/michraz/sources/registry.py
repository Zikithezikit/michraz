"""The built-in sources, in search order."""

from __future__ import annotations

from typing import Any

from michraz.sources.base import BaseSource
from michraz.sources.beersheva import BeerShevaSource
from michraz.sources.gov import GovSource
from michraz.sources.municipal import (
    AkkoSource,
    AradSource,
    BetShemeshSource,
    DimonaSource,
    KfarSabaSource,
    KiryatMotzkinSource,
    NesherSource,
    NetivotSource,
    NofHaGalilSource,
    SavyonSource,
    TamraSource,
    YavneSource,
)
from michraz.sources.rmi import RmiSource

BUILT_IN: tuple[type[BaseSource[Any]], ...] = (
    RmiSource,
    BeerShevaSource,
    GovSource,
    AkkoSource,
    AradSource,
    BetShemeshSource,
    DimonaSource,
    KfarSabaSource,
    KiryatMotzkinSource,
    NesherSource,
    NetivotSource,
    NofHaGalilSource,
    SavyonSource,
    TamraSource,
    YavneSource,
)
"""Every built-in source class. Its order matches :class:`SourceName`."""


def default_sources(**settings: Any) -> tuple[BaseSource[Any], ...]:
    """Returns one instance of every built-in source.

    Args:
        **settings: ``cache_dir``, ``cache_ttl`` and ``min_interval``, passed to each source.
    """
    return tuple(source(**settings) for source in BUILT_IN)
