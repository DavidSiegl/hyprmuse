"""base.Client: request spacing and error reporting."""

import pytest
import requests

from hyprmuse.sources import base
from hyprmuse.sources.base import Client, SourceError


class Clock:
    """A fake monotonic clock that time.sleep advances."""

    def __init__(self):
        self.now = 100.0
        self.slept = []

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(base.time, "monotonic", lambda: clock.now)
    monkeypatch.setattr(base.time, "sleep", clock.sleep)
    return clock


def respond(monkeypatch, http_status=200, error=None):
    """Make requests.get answer with ``http_status``, or raise ``error``.

    Returns the list each call's (args, kwargs) is appended to.
    """
    calls = []

    class Response:
        status_code = http_status

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        if error:
            raise error
        return Response()

    monkeypatch.setattr(base.requests, "get", get)
    return calls


def test_sends_params_a_user_agent_and_a_timeout(monkeypatch, clock):
    calls = respond(monkeypatch)
    Client().get("https://example.org/api", params={"q": "x"})
    ((args, kwargs),) = calls
    assert args == ("https://example.org/api",)
    assert kwargs["params"] == {"q": "x"}
    assert kwargs["headers"] == {"User-Agent": base.USER_AGENT}
    assert kwargs["timeout"] == base.TIMEOUT


def test_first_request_does_not_wait(monkeypatch, clock):
    respond(monkeypatch)
    Client(gap=5.0).get("https://example.org")
    assert clock.slept == []


def test_next_request_waits_out_the_rest_of_the_gap(monkeypatch, clock):
    respond(monkeypatch)
    client = Client(gap=5.0)
    client.get("https://example.org")
    clock.now += 2.0
    client.get("https://example.org")
    assert clock.slept == [pytest.approx(3.0)]


def test_jitter_adds_at_most_its_bound(monkeypatch, clock):
    respond(monkeypatch)
    client = Client(gap=1.0, jitter=1.5)
    for _ in range(20):
        client.get("https://example.org")
    assert all(1.0 <= s <= 2.5 for s in clock.slept)
    assert len(clock.slept) == 19


def test_a_failed_request_still_counts_for_the_gap(monkeypatch, clock):
    client = Client(gap=5.0)
    respond(monkeypatch, error=requests.ConnectionError("down"))
    with pytest.raises(SourceError, match="request to https://example.org failed"):
        client.get("https://example.org")
    respond(monkeypatch)
    client.get("https://example.org")
    assert clock.slept == [pytest.approx(5.0)]


def test_non_200_is_a_source_error(monkeypatch, clock):
    respond(monkeypatch, http_status=429)
    with pytest.raises(SourceError, match="HTTP 429"):
        Client().get("https://example.org")
