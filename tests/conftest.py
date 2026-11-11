"""Shared fixtures. Every test runs against a temporary store, never ~/."""

import pytest
import requests

from hyprmuse import config
from hyprmuse.sources.base import Item, NotFound, SourceError, Subject


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    """Redirect all XDG paths into tmp_path for the duration of a test."""
    data = tmp_path / "data"
    conf = tmp_path / "conf"
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "CONFIG_DIR", conf)
    monkeypatch.setattr(config, "SUBJECTS_DIR", data / "subjects")
    monkeypatch.setattr(config, "RECENT_FILE", data / "recent.json")
    monkeypatch.setattr(config, "CONFIG_FILE", conf / "config.toml")
    monkeypatch.delenv(config.GENIUS_TOKEN_ENV, raising=False)
    return tmp_path


@pytest.fixture
def genius_token(monkeypatch):
    """Set a Genius API access token in the environment, and return it."""
    monkeypatch.setenv(config.GENIUS_TOKEN_ENV, "test-token")
    return "test-token"


class FakeResponse:
    """Stands in for a requests.Response."""

    def __init__(self, payload=None, text="", encoding="utf-8"):
        self._payload = payload
        self.text = text
        self.encoding = encoding
        self.status_code = 200

    def json(self):
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload


@pytest.fixture
def fake_response():
    return FakeResponse


class FakeClient:
    """Stands in for a source's ``base.Client``, answering from canned responses.

    ``routes`` maps a full URL (see ``url``) to the FakeResponse to return for
    it, or to a SourceError to raise in its place. A URL with no route raises
    NotFound, as an HTTP 404 would. ``requested`` lists every full URL asked
    for, in order, and ``tokens`` the access token each of them carried (None
    for none) at the same index.
    """

    def __init__(self, routes):
        self.routes = routes
        self.requested = []
        self.tokens = []

    @staticmethod
    def url(url, params=None):
        """``url`` with ``params`` in its query string, as requests sends it."""
        return requests.Request("GET", url, params=params).prepare().url

    def get(self, url, params=None, token=None):
        url = self.url(url, params)
        self.requested.append(url)
        self.tokens.append(token)
        if url not in self.routes:
            raise NotFound(f"{url} returned HTTP 404")
        reply = self.routes[url]
        if isinstance(reply, SourceError):
            raise reply
        return reply


def make_subject(source="genius", source_id="1", name="Test Subject",
                 domain="music", lang="en", items=None, atomic=False,
                 n_items=3, n_lines=6):
    """A subject with predictable, synthetic content."""
    if items is None:
        items = [
            Item(lines=[f"line {i}-{j}" for j in range(n_lines)],
                 work=f"Work {i}", atomic=atomic)
            for i in range(n_items)
        ]
    return Subject(source=source, source_id=source_id, name=name,
                   domain=domain, lang=lang, items=items)


@pytest.fixture
def fake_client():
    return FakeClient
