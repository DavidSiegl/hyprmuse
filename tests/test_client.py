"""base.Client: request spacing and error reporting."""

import pytest
import requests

from hyprmuse.sources import REGISTRY, base
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
    assert kwargs["headers"] == {"User-Agent": base.BROWSER_USER_AGENT}
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


def test_jitter_draws_up_to_its_bound_and_adds_it_to_the_gap(monkeypatch, clock):
    respond(monkeypatch)
    bounds = []

    def uniform(low, high):
        bounds.append((low, high))
        return 0.7

    monkeypatch.setattr(base.random, "uniform", uniform)
    client = Client(gap=1.0, jitter=1.5)
    client.get("https://example.org")
    client.get("https://example.org")
    assert bounds == [(0.0, 1.5)]
    assert clock.slept == [pytest.approx(1.7)]


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


class EmptyResponse:
    """A 200 every source's search reads as no hits."""

    status_code = 200
    text = ""

    def json(self):
        return {}


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_only_wikiquote_identifies_as_hyprmuse(monkeypatch, clock, name):
    agents = []

    def get(*_, headers, **__):
        agents.append(headers["User-Agent"])
        return EmptyResponse()

    monkeypatch.setattr(base.requests, "get", get)
    REGISTRY[name].search("anything", "en")
    expected = base.hyprmuse_user_agent() if name == "wikiquote" else base.BROWSER_USER_AGENT
    assert agents == [expected]


def test_hyprmuse_agent_names_the_version_and_a_contact(monkeypatch):
    monkeypatch.setattr(base.metadata, "version", lambda _: "1.2.3")
    assert base.hyprmuse_user_agent() == "hyprmuse/1.2.3 (https://github.com/DavidSiegl/hyprmuse)"


def test_hyprmuse_agent_without_package_metadata(monkeypatch):
    def missing(name):
        raise base.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(base.metadata, "version", missing)
    assert base.hyprmuse_user_agent() == "hyprmuse (https://github.com/DavidSiegl/hyprmuse)"
