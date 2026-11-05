import dataclasses
from datetime import date, datetime, timedelta

import pytest

from michraz.filters import TenderFilter, apply_filters, matches_keyword, normalize, sort_by_deadline
from tests.helpers import at, make_tender

NOW = at(2026, 11, 4, 12, 0)


def test_hebrew_keyword_matches_title():
    t = make_tender(title="הקמה, תחזוקה ושיקום שטחי גינון")
    assert matches_keyword(t, "גינון")
    assert not matches_keyword(t, "הגברה")


def test_keyword_matches_number():
    assert matches_keyword(make_tender(number="33/2026"), "33/2026")


def test_keyword_is_case_insensitive():
    assert matches_keyword(make_tender(title="Gardening Services"), "gARDEN")


def test_keyword_uses_nfkc():
    # fullwidth "ＡＢＣ" and the "ﬁ" ligature fold to plain ASCII
    assert matches_keyword(make_tender(title="ＡＢＣ tender"), "abc")
    assert matches_keyword(make_tender(title="ofﬁce"), "office")
    assert normalize("ﬁ") == "fi"


def test_keyword_is_trimmed():
    assert matches_keyword(make_tender(title="גינון"), "  גינון ")


def test_apply_filters_combines_conditions():
    tenders = [
        make_tender(source_id="1", title="גינון", deadline=at(2026, 12, 1)),
        make_tender(source_id="2", title="גינון", deadline=at(2026, 11, 1)),
        make_tender(source_id="3", title="הגברה", deadline=at(2026, 12, 1)),
    ]
    kept = apply_filters(tenders, keyword="גינון", open_only=True, now=NOW)
    assert [t.source_id for t in kept] == ["1"]


def test_no_conditions_keeps_everything_in_order():
    tenders = [make_tender(source_id=str(i)) for i in range(3)]
    assert apply_filters(tenders) == tenders


def test_closing_bounds_with_datetimes():
    early, late = (
        make_tender(source_id="e", deadline=at(2026, 11, 10)),
        make_tender(source_id="l", deadline=at(2026, 12, 10)),
    )
    assert apply_filters([early, late], closing_before=at(2026, 12, 1)) == [early]
    assert apply_filters([early, late], closing_after=at(2026, 12, 1)) == [late]


def test_closing_bound_is_exclusive_before_and_inclusive_after():
    t = make_tender(deadline=at(2026, 12, 1))
    assert apply_filters([t], closing_before=at(2026, 12, 1)) == []
    assert apply_filters([t], closing_after=at(2026, 12, 1)) == [t]


def test_plain_dates_mean_midnight_in_jerusalem():
    t = make_tender(deadline=at(2026, 12, 1, 12))
    assert apply_filters([t], closing_after=date(2026, 12, 1)) == [t]
    assert apply_filters([t], closing_before=date(2026, 12, 1)) == []
    assert apply_filters([t], closing_before=date(2026, 12, 2)) == [t]


def test_unknown_deadline_never_matches_a_closing_bound():
    t = make_tender(deadline=None)
    assert apply_filters([t], closing_before=at(2030, 1, 1)) == []
    assert apply_filters([t], closing_after=at(2000, 1, 1)) == []


def test_naive_bound_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        apply_filters([], closing_before=datetime(2026, 12, 1))


def test_sort_puts_unknown_deadlines_last_and_is_stable():
    a = make_tender(source_id="a", deadline=at(2026, 12, 1))
    b = make_tender(source_id="b", deadline=at(2026, 11, 1))
    none1 = make_tender(source_id="n1")
    none2 = make_tender(source_id="n2")
    assert [t.source_id for t in sort_by_deadline([none1, a, none2, b])] == ["b", "a", "n1", "n2"]


def test_tender_filter_is_reusable_and_immutable():
    criteria = TenderFilter(keyword="גינון", open_only=True, now=NOW)
    open_t = make_tender(title="גינון", deadline=NOW + timedelta(days=1))
    closed = make_tender(source_id="2", title="גינון", deadline=NOW - timedelta(days=1))
    assert criteria.apply([open_t, closed]) == [open_t]
    assert criteria.matches(open_t) and not criteria.matches(closed)
    with pytest.raises(dataclasses.FrozenInstanceError):
        criteria.keyword = "x"  # type: ignore[misc]


def test_tender_filter_rejects_naive_bounds_on_creation():
    with pytest.raises(ValueError, match="timezone-aware"):
        TenderFilter(closing_before=datetime(2026, 12, 1))
    with pytest.raises(ValueError, match="timezone-aware"):
        TenderFilter(now=datetime(2026, 12, 1))


def test_kind_filter_keeps_only_that_kind():
    from michraz import TenderKind

    tender = make_tender(source_id="1")
    vacancy = make_tender(source_id="2", kind=TenderKind.VACANCY)
    assert apply_filters([tender, vacancy], kind=TenderKind.TENDER) == [tender]
    assert apply_filters([tender, vacancy], kind=TenderKind.VACANCY) == [vacancy]
    assert apply_filters([tender, vacancy]) == [tender, vacancy]
