import dataclasses
from datetime import datetime

import pytest

from michraz import Document, Tender
from tests.helpers import at, make_tender

NOW = at(2026, 11, 4, 12, 0)


def test_key_is_source_and_id():
    assert make_tender(source="rmi", source_id="7").key == ("rmi", "7")


def test_tender_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        make_tender().title = "other"  # type: ignore[misc]


def test_tender_is_hashable_and_extra_does_not_affect_equality():
    a = make_tender(extra={"raw": {"x": 1}})
    b = make_tender(extra={"raw": {"x": 2}})
    assert a == b and hash(a) == hash(b)


def test_defaults_are_empty():
    t = make_tender()
    assert t.documents == () and dict(t.extra) == {} and t.deadline is None and t.winner is None


def test_required_fields_must_be_named():
    with pytest.raises(TypeError):
        Tender("rmi", "1", "title", "credit")  # type: ignore[misc]


def test_document_holds_title_and_url():
    assert Document("a", "http://x") == Document(title="a", url="http://x")


def test_open_when_deadline_in_future_and_no_winner():
    assert make_tender(deadline=at(2026, 11, 5)).is_open(NOW)


def test_closed_when_deadline_equals_now():
    assert not make_tender(deadline=NOW).is_open(NOW)


def test_closed_when_deadline_passed():
    assert not make_tender(deadline=at(2026, 11, 3)).is_open(NOW)


def test_closed_when_there_is_a_winner():
    assert not make_tender(deadline=at(2026, 12, 1), winner="Acme").is_open(NOW)


def test_unknown_deadline_is_closed():
    assert not make_tender(deadline=None).is_open(NOW)


def test_is_open_uses_the_current_time_by_default():
    assert make_tender(deadline=at(2999, 1, 1)).is_open()
    assert not make_tender(deadline=at(2000, 1, 1)).is_open()


def test_naive_now_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        make_tender(deadline=at(2026, 12, 1)).is_open(datetime(2026, 11, 4))
