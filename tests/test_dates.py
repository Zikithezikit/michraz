from datetime import timedelta

import pytest

from michraz._dates import JERUSALEM, parse_iso, parse_local


def test_parse_iso_converts_to_jerusalem_and_keeps_the_instant():
    parsed = parse_iso("2026-12-28T12:00:00+02:00")
    assert parsed is not None and parsed.tzinfo is JERUSALEM
    assert (parsed.year, parsed.month, parsed.day, parsed.hour) == (2026, 12, 28, 12)


def test_parse_iso_summer_offset():
    parsed = parse_iso("2017-05-11T00:00:00+03:00")
    assert parsed is not None and parsed.utcoffset() == timedelta(hours=3)


def test_parse_iso_other_offsets_are_converted():
    parsed = parse_iso("2026-12-28T10:00:00Z")
    assert parsed is not None and parsed.hour == 12 and parsed.utcoffset() == timedelta(hours=2)


def test_parse_iso_naive_is_read_as_jerusalem():
    parsed = parse_iso("2026-12-28T12:00:00")
    assert parsed is not None and parsed.tzinfo is JERUSALEM and parsed.hour == 12


@pytest.mark.parametrize("fraction", ["5", "55", "857", "857123", "8571234"])
def test_parse_iso_fractional_seconds_of_any_length(fraction):
    # Python 3.10 rejects fractions that are not 3 or 6 digits; real RMI data has 2.
    parsed = parse_iso(f"2025-11-26T12:54:57.{fraction}+02:00")
    assert parsed is not None and parsed.second == 57 and parsed.microsecond == int(fraction[:6].ljust(6, "0"))


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_blank_values_are_none(blank):
    assert parse_iso(blank) is None
    assert parse_local(blank) is None


def test_parse_iso_rejects_garbage():
    with pytest.raises(ValueError):
        parse_iso("not a date")


def test_parse_local_is_jerusalem_with_dst():
    winter = parse_local("10/11/2026 12:00:00")
    summer = parse_local("10/07/2026 12:00:00")
    assert winter is not None and winter.utcoffset() == timedelta(hours=2)
    assert summer is not None and summer.utcoffset() == timedelta(hours=3)
    assert winter.day == 10 and winter.month == 11


def test_parse_local_rejects_wrong_format():
    with pytest.raises(ValueError):
        parse_local("2026-11-10 12:00:00")
