"""Shared fixtures. Every test runs against a temporary store, never ~/."""

import pytest
import requests

from hyprmuse import config
from hyprmuse.sources.base import Item, SourceError, Subject


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
    return tmp_path


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
    it. A URL with no route raises SourceError, as an HTTP error would.
    ``requested`` lists every full URL asked for, in order.
    """

    def __init__(self, routes):
        self.routes = routes
        self.requested = []

    @staticmethod
    def url(url, params=None):
        """``url`` with ``params`` in its query string, as requests sends it."""
        return requests.Request("GET", url, params=params).prepare().url

    def get(self, url, params=None):
        url = self.url(url, params)
        self.requested.append(url)
        if url not in self.routes:
            raise SourceError(f"{url} returned HTTP 404")
        return self.routes[url]


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
