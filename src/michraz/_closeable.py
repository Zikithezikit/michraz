"""Context-manager behaviour shared by every object that owns a connection pool."""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import TypeVar

_T = TypeVar("_T", bound="Closeable")


class Closeable(ABC):
    """An object with a :meth:`close` method that can be used in a ``with`` block."""

    @abstractmethod
    def close(self) -> None:
        """Releases the resources this object owns."""

    def __enter__(self: _T) -> _T:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()
