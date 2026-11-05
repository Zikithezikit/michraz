import socket
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest

from michraz._dates import JERUSALEM
from michraz._http import HttpClient
from tests.helpers import FakeClock, load_fixture


@pytest.fixture(autouse=True)
def _pinned_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixes "now" to the day the fixtures were recorded, so open/closed results do not drift."""
    monkeypatch.setattr("michraz._dates.now", lambda: datetime(2026, 11, 4, 12, 0, tzinfo=JERUSALEM))


@pytest.fixture(autouse=True)
def _no_real_sleep(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Skips the rate-limit wait of clients built inside a test. Live tests keep the real wait."""
    if not request.node.get_closest_marker("live"):
        monkeypatch.setattr("time.sleep", lambda seconds: None)


@pytest.fixture(autouse=True)
def _no_real_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails any test that tries to open a real socket, unless it is marked ``live``."""
    if request.node.get_closest_marker("live"):
        return

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("tests must not touch the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_http(clock: FakeClock) -> Callable[..., HttpClient]:
    def factory(**kwargs: Any) -> HttpClient:
        kwargs.setdefault("cache_dir", None)
        return HttpClient(clock=clock, sleep=clock.sleep, wall_clock=clock, **kwargs)

    return factory


@pytest.fixture
def http(make_http: Callable[..., HttpClient]) -> HttpClient:
    return make_http()


@pytest.fixture
def rmi_records() -> list[dict[str, Any]]:
    return load_fixture("rmi_search.json")  # type: ignore[no-any-return]


@pytest.fixture
def bs_records() -> list[dict[str, Any]]:
    return load_fixture("beersheva.json")  # type: ignore[no-any-return]
