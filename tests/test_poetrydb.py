"""PoetryDB author matching and fetch shaping."""

import pytest

from hyprmuse.sources import poetrydb
from hyprmuse.sources.base import SourceError

AUTHORS = {"authors": ["Emily Dickinson", "Walt Whitman", "William Blake"]}
POEMS = [
    {"title": "First Poem", "author": "Emily Dickinson",
     "lines": ["a line", "another line", "", "  ", "a third line"]},
    {"title": "Empty Poem", "author": "Emily Dickinson", "lines": ["", "   "]},
]


def source(fake_client, fake_response, routes):
    """A PoetryDB answering each API path in ``routes`` with its JSON payload."""
    return poetrydb.PoetryDB(fake_client(
        {fake_client.url(poetrydb.API + path): fake_response(payload)
         for path, payload in routes.items()}))


def test_search_matches_on_substring(fake_client, fake_response):
    hits = source(fake_client, fake_response, {"/author": AUTHORS}).search("dickinson", "en")
    assert hits[0].name == "Emily Dickinson"
    assert hits[0].source_id == "Emily Dickinson"


def test_search_falls_back_to_fuzzy_matching(fake_client, fake_response):
    hits = source(fake_client, fake_response, {"/author": AUTHORS}).search("Walt Whitmn", "en")  # typo
    assert hits and hits[0].name == "Walt Whitman"


def test_search_returns_nothing_for_a_miss(fake_client, fake_response):
    assert source(fake_client, fake_response, {"/author": AUTHORS}).search("zzzzzzzz", "en") == []


def test_fetch_builds_sliceable_items_and_keeps_one_stanza_break(
        fake_client, fake_response):
    subject = source(fake_client, fake_response, {
        "/author/Emily Dickinson/title,author,lines": POEMS}).fetch("Emily Dickinson")
    assert len(subject.items) == 1              # the empty poem is dropped
    assert subject.items[0].atomic is False     # poems are sliceable
    assert subject.items[0].lines == ["a line", "another line", "", "a third line"]
    assert subject.items[0].work == "First Poem"
    assert subject.attribution["license"] == "public domain"


def test_fetch_raises_when_api_reports_a_miss(fake_client, fake_response):
    src = source(fake_client, fake_response, {
        "/author/Nobody/title,author,lines": {"status": 404}})
    with pytest.raises(SourceError):
        src.fetch("Nobody")
