"""Enum base used across the package."""

from enum import Enum


class StrEnum(str, Enum):
    """A string enum whose members equal, hash and print as their values.

    ``StrEnum.MEMBER == "value"`` is true and members work as dictionary keys next to plain strings, so code
    that still passes the raw string keeps working. ``enum.StrEnum`` exists only from Python 3.11.
    """

    def __str__(self) -> str:
        return str(self.value)
