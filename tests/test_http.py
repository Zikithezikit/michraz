import json
from datetime import timedelta

import httpx
import pytest

from michraz._http import MAX_RETRIES, USER_AGENT, HttpClient
from michraz.errors import SourceFormatError, SourceUnavailableError

URL = "https://example.test/api"


def test_user_agent_is_honest(respx_mock, http):
    route = respx_mock.get(URL).respond(json={})
    http.get_json("t", URL)
    sent = route.calls.last.request.headers["user-agent"]
    assert sent == USER_AGENT
    assert sent.startswith("michraz/") and "github.com/Zikithezikit/michraz" in sent


def test_get_passes_query_parameters(respx_mock, http):
    route = respx_mock.get(URL).respond(json={"ok": True})
    assert http.get_json("t", URL, {"limit": 5, "offset": 10}) == {"ok": True}
    assert dict(route.calls.last.request.url.params) == {"limit": "5", "offset": "10"}


def test_post_sends_json(respx_mock, http):
    route = respx_mock.post(URL).respond(json=[1])
    assert http.post_json("t", URL, {"a": "ש"}) == [1]
    assert json.loads(route.calls.last.request.content) == {"a": "ש"}


def test_retries_503_then_succeeds(respx_mock, http, clock):
    route = respx_mock.get(URL).mock(side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": 1})])
    assert http.get_json("t", URL) == {"ok": 1}
    assert route.call_count == 2
    assert clock.sleeps == [1.0]


def test_backoff_is_exponential_and_bounded(respx_mock, http, clock):
    route = respx_mock.get(URL).respond(500)
    with pytest.raises(SourceUnavailableError, match="HTTP 500"):
        http.get_json("t", URL)
    assert route.call_count == MAX_RETRIES + 1
    assert clock.sleeps == [1.0, 2.0]


def test_429_honors_retry_after_seconds(respx_mock, http, clock):
    respx_mock.get(URL).mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json={})]
    )
    http.get_json("t", URL)
    assert clock.sleeps == [7.0]


def test_retry_after_http_date(respx_mock, http, clock):
    clock.now = 1_700_000_000.0  # Tue, 14 Nov 2023 22:13:20 GMT
    respx_mock.get(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "Tue, 14 Nov 2023 22:13:30 GMT"}),
            httpx.Response(200, json={}),
        ]
    )
    http.get_json("t", URL)
    assert clock.sleeps == [pytest.approx(10.0)]


def test_unparseable_retry_after_falls_back_to_backoff(respx_mock, http, clock):
    respx_mock.get(URL).mock(
        side_effect=[httpx.Response(503, headers={"Retry-After": "soon"}), httpx.Response(200, json={})]
    )
    http.get_json("t", URL)
    assert clock.sleeps == [1.0]


def test_gives_up_when_asked_to_wait_too_long(respx_mock, http, clock):
    route = respx_mock.get(URL).respond(429, headers={"Retry-After": "3600"})
    with pytest.raises(SourceUnavailableError, match="asked to wait"):
        http.get_json("t", URL)
    assert route.call_count == 1 and clock.sleeps == []


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410])
def test_never_retries_client_errors(respx_mock, http, status):
    route = respx_mock.get(URL).respond(status)
    with pytest.raises(SourceUnavailableError, match=f"HTTP {status}"):
        http.get_json("t", URL)
    assert route.call_count == 1


def test_redirects_are_errors_not_followed(respx_mock, http):
    respx_mock.get(URL).respond(302, headers={"Location": "https://elsewhere.test/"})
    with pytest.raises(SourceUnavailableError, match="HTTP 302"):
        http.get_json("t", URL)


def test_transport_errors_become_source_unavailable(respx_mock, http):
    respx_mock.get(URL).mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(SourceUnavailableError, match="example.test") as info:
        http.get_json("rmi", URL)
    assert info.value.source == "rmi"


def test_malformed_json_raises_format_error_with_truncated_sample(respx_mock, http):
    respx_mock.get(URL).respond(200, text="<html>" + "x" * 1000)
    with pytest.raises(SourceFormatError) as info:
        http.get_json("rmi", URL)
    message = str(info.value)
    assert message.startswith("rmi: response is not JSON") and "<html>" in message
    assert len(message) < 400


def test_cache_hit_makes_no_second_request(respx_mock, make_http, tmp_path):
    route = respx_mock.get(URL).respond(json={"n": 1})
    client = make_http(cache_dir=tmp_path)
    assert client.get_json("t", URL) == {"n": 1}
    assert client.get_json("t", URL) == {"n": 1}
    assert route.call_count == 1


def test_cache_survives_a_new_client(respx_mock, make_http, tmp_path):
    route = respx_mock.get(URL).respond(json={"n": 1})
    make_http(cache_dir=tmp_path).get_json("t", URL)
    assert make_http(cache_dir=tmp_path).get_json("t", URL) == {"n": 1}
    assert route.call_count == 1


def test_cache_expires_after_ttl(respx_mock, make_http, tmp_path, clock):
    route = respx_mock.get(URL).respond(json={"n": 1})
    client = make_http(cache_dir=tmp_path, cache_ttl=timedelta(minutes=10))
    client.get_json("t", URL)
    clock.now += 599
    client.get_json("t", URL)
    assert route.call_count == 1
    clock.now += 2
    client.get_json("t", URL)
    assert route.call_count == 2


def test_cache_key_includes_body_and_params(respx_mock, make_http, tmp_path):
    route = respx_mock.post(URL).respond(json=[])
    client = make_http(cache_dir=tmp_path)
    client.post_json("t", URL, {"a": 1})
    client.post_json("t", URL, {"a": 1})
    client.post_json("t", URL, {"a": 2})
    assert route.call_count == 2
    get = respx_mock.get(URL).respond(json=[])
    client.get_json("t", URL, {"offset": 0})
    client.get_json("t", URL, {"offset": 100})
    assert get.call_count == 2


def test_failures_are_not_cached(respx_mock, make_http, tmp_path):
    route = respx_mock.get(URL).mock(side_effect=[httpx.Response(404), httpx.Response(200, json={"ok": 1})])
    client = make_http(cache_dir=tmp_path)
    with pytest.raises(SourceUnavailableError):
        client.get_json("t", URL)
    assert client.get_json("t", URL) == {"ok": 1}
    assert route.call_count == 2


def test_corrupt_cache_file_is_a_miss(respx_mock, make_http, tmp_path):
    route = respx_mock.get(URL).respond(json={"n": 1})
    client = make_http(cache_dir=tmp_path)
    client.get_json("t", URL)
    for file in tmp_path.glob("*.json"):
        file.write_text("{not json", encoding="utf-8")
    assert client.get_json("t", URL) == {"n": 1}
    assert route.call_count == 2


def test_unwritable_cache_never_breaks_a_request(respx_mock, make_http, tmp_path):
    respx_mock.get(URL).respond(json={"n": 1})
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    assert make_http(cache_dir=blocker / "sub").get_json("t", URL) == {"n": 1}


def test_cache_disabled_always_hits_the_network(respx_mock, make_http):
    route = respx_mock.get(URL).respond(json={})
    client = make_http(cache_dir=None)
    client.get_json("t", URL)
    client.get_json("t", URL)
    assert route.call_count == 2


def test_cached_at_reports_the_fetch_time(respx_mock, make_http, tmp_path, clock):
    respx_mock.get(URL).respond(json={})
    client = make_http(cache_dir=tmp_path)
    assert client.cached_at("GET", URL) is None
    client.get_json("t", URL)
    stamp = client.cached_at("GET", URL)
    assert stamp is not None and stamp.timestamp() == clock.now
    assert make_http(cache_dir=None).cached_at("GET", URL) is None


def test_rate_limit_waits_between_requests_to_one_host(respx_mock, http, clock):
    respx_mock.get(URL).respond(json={})
    http.get_json("t", URL, {"i": 1})
    http.get_json("t", URL, {"i": 2})
    http.get_json("t", URL, {"i": 3})
    assert clock.sleeps == [1.0, 1.0]


def test_rate_limit_counts_time_already_spent(respx_mock, http, clock):
    respx_mock.get(URL).respond(json={})
    http.get_json("t", URL, {"i": 1})
    clock.now += 0.4
    http.get_json("t", URL, {"i": 2})
    assert clock.sleeps == [pytest.approx(0.6)]


def test_rate_limit_is_per_host(respx_mock, http, clock):
    respx_mock.get(URL).respond(json={})
    respx_mock.get("https://other.test/api").respond(json={})
    http.get_json("t", URL)
    http.get_json("t", "https://other.test/api")
    assert clock.sleeps == []


def test_cache_hits_do_not_count_against_the_rate_limit(respx_mock, make_http, tmp_path, clock):
    respx_mock.get(URL).respond(json={})
    client = make_http(cache_dir=tmp_path)
    client.get_json("t", URL)
    client.get_json("t", URL)
    assert clock.sleeps == []


def test_interval_can_be_raised_but_not_below_the_floor(respx_mock, make_http, clock):
    respx_mock.get(URL).respond(json={})
    slow = make_http(min_interval=3.0)
    slow.get_json("t", URL, {"i": 1})
    slow.get_json("t", URL, {"i": 2})
    assert clock.sleeps == [3.0]
    with pytest.raises(ValueError, match="0.5"):
        HttpClient(min_interval=0.4)
    assert make_http(min_interval=0.5).min_interval == 0.5


def test_context_manager_closes_an_owned_client():
    with HttpClient(cache_dir=None) as client:
        inner = client._client
    assert inner.is_closed


def test_a_supplied_client_is_left_open():
    own = httpx.Client()
    HttpClient(cache_dir=None, client=own).close()
    assert not own.is_closed
    own.close()
