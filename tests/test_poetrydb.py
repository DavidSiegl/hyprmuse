"""PoetryDB author matching and fetch shaping."""

import pytest

from hyprmuse.sources import poetrydb
from hyprmuse.sources.base import Candidate, SourceError

AUTHORS = {"authors": ["Emily Dickinson", "Walt Whitman", "William Blake"]}
POEMS = [
    {"title": "First Poem", "author": "Emily Dickinson",
     "lines": ["a line", "another line", "", "  ", "a third line"]},
    {"title": "Empty Poem", "author": "Emily Dickinson", "lines": ["", "   "]},
]


def test_search_matches_on_substring(monkeypatch, fake_response):
    monkeypatch.setattr(poetrydb, "get", lambda *a, **k: fake_response(AUTHORS))
    hits = poetrydb.SOURCE.search("dickinson", "en")
    assert hits[0].name == "Emily Dickinson"
    assert hits[0].source_id == "Emily Dickinson"


def test_search_falls_back_to_fuzzy_matching(monkeypatch, fake_response):
    monkeypatch.setattr(poetrydb, "get", lambda *a, **k: fake_response(AUTHORS))
    hits = poetrydb.SOURCE.search("Walt Whitmn", "en")  # typo
    assert hits and hits[0].name == "Walt Whitman"


def test_search_returns_nothing_for_a_miss(monkeypatch, fake_response):
    monkeypatch.setattr(poetrydb, "get", lambda *a, **k: fake_response(AUTHORS))
    assert poetrydb.SOURCE.search("zzzzzzzz", "en") == []


def test_fetch_builds_sliceable_items_and_keeps_one_stanza_break(
        monkeypatch, fake_response):
    monkeypatch.setattr(poetrydb, "get", lambda *a, **k: fake_response(POEMS))
    cand = Candidate(source="poetrydb", source_id="Emily Dickinson",
                     name="Emily Dickinson", domain="poetry")
    subject = poetrydb.SOURCE.fetch(cand)
    assert len(subject.items) == 1              # the empty poem is dropped
    assert subject.items[0].atomic is False     # poems are sliceable
    assert subject.items[0].lines == ["a line", "another line", "", "a third line"]
    assert subject.items[0].work == "First Poem"
    assert subject.attribution["license"] == "public domain"


def test_fetch_raises_when_api_reports_a_miss(monkeypatch, fake_response):
    monkeypatch.setattr(poetrydb, "get",
                        lambda *a, **k: fake_response({"status": 404}))
    cand = Candidate(source="poetrydb", source_id="Nobody", name="Nobody",
                     domain="poetry")
    with pytest.raises(SourceError):
        poetrydb.SOURCE.fetch(cand)
