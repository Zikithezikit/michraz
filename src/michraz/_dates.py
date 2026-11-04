"""Date parsing helpers. Every datetime michraz produces is timezone-aware."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

JERUSALEM = ZoneInfo("Asia/Jerusalem")

LOCAL_FORMAT = "%d/%m/%Y %H:%M:%S"

_FRACTION = re.compile(r"\.(\d+)")
MICROSECOND_DIGITS = 6


def _pad_fraction(match: re.Match[str]) -> str:
    # Python 3.10 only accepts fractions of exactly 3 or 6 digits; the RMI API sends 2 ("57.55").
    return "." + match.group(1)[:MICROSECOND_DIGITS].ljust(MICROSECOND_DIGITS, "0")


def parse_iso(value: str | None) -> datetime | None:
    """Parses an ISO 8601 timestamp and converts it to Asia/Jerusalem.

    Args:
        value: Timestamp such as ``"2026-12-28T12:00:00+02:00"``. A value without an offset is taken as
            Asia/Jerusalem local time.

    Returns:
        An aware datetime, or None if ``value`` is None or blank.

    Raises:
        ValueError: If ``value`` is not a valid ISO 8601 timestamp.
    """
    if value is None or not value.strip():
        return None
    text = _FRACTION.sub(_pad_fraction, value.strip().replace("Z", "+00:00"))
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=JERUSALEM)
    return parsed.astimezone(JERUSALEM)


def parse_local(value: str | None, fmt: str = LOCAL_FORMAT) -> datetime | None:
    """Parses a local Israeli timestamp such as ``"10/11/2026 12:00:00"``.

    Args:
        value: Text to parse.
        fmt: ``strptime`` format. Defaults to ``dd/mm/yyyy HH:MM:SS``.

    Returns:
        An aware datetime in Asia/Jerusalem, or None if ``value`` is None or blank.

    Raises:
        ValueError: If ``value`` does not match ``fmt``.
    """
    if value is None or not value.strip():
        return None
    return datetime.strptime(value.strip(), fmt).replace(tzinfo=JERUSALEM)


def now() -> datetime:
    """Returns the current time in Asia/Jerusalem."""
    return datetime.now(JERUSALEM)
