"""A reply that is not what a source expects is a SourceError, not a traceback."""

import json

import pytest

from hyprmuse.sources import REGISTRY, base
from hyprmuse.sources.base import Client, SourceError

# The sources that read JSON, and an id each one's fetch accepts.
JSON_SOURCES = {"genius": "7", "poetrydb": "Emily Dickinson", "wikiquote": "en:Somebody"}

BODIES = {
    "html": "<html><body>Down for maintenance</body></html>",
    "list": json.dumps([1, 2]),
    "keys": json.dumps({"response": {"songs": [{}], "hits": [5]}, "query": {"search": [{}]},
                        "parse": {}, "authors": 5}),
}


@pytest.fixture
def answer(monkeypatch):
    """Make every request get HTTP 200 with the body passed in.

    Returns the function that installs the body; the URLs requested are
    appended to its ``urls`` list.
    """
    def answer_with(body):
        class Response:
            status_code = 200
            text = body
            encoding = "utf-8"

            def json(self):
                return json.loads(body)

        def get(url, *_, **__):
            answer_with.urls.append(url)
            return Response()

        monkeypatch.setattr(base.requests, "get", get)
    answer_with.urls = []
    return answer_with


@pytest.mark.parametrize("body", sorted(BODIES))
@pytest.mark.parametrize("name", sorted(JSON_SOURCES))
@pytest.mark.parametrize("call", ["search", "fetch"])
@pytest.mark.usefixtures("genius_token")
def test_unexpected_reply_is_a_source_error(answer, name, body, call):
    answer(BODIES[body])
    src = type(REGISTRY[name])(Client())
    with pytest.raises(SourceError) as err:
        if call == "search":
            src.search("anything", "en")
        else:
            src.fetch(JSON_SOURCES[name])
    # The error names the source and the URL whose reply it could not read.
    msg = str(err.value)
    assert msg.startswith(f"{name}: unexpected reply from {answer.urls[-1]}")


@pytest.mark.parametrize("authors", [[None, {"name": "X"}], "Emily Dickinson"])
def test_poetrydb_authors_that_are_not_strings_are_a_source_error(answer, authors):
    answer(json.dumps({"authors": authors}))
    with pytest.raises(SourceError, match="poetrydb: unexpected reply"):
        type(REGISTRY["poetrydb"])(Client()).search("dickinson")


@pytest.mark.parametrize("poem", [{"title": "Hope", "lines": "Hope is the thing"},
                                  {"title": None, "lines": ["Hope"]}])
def test_poetrydb_poem_of_the_wrong_shape_is_a_source_error(answer, poem):
    answer(json.dumps([poem]))
    with pytest.raises(SourceError, match="poetrydb: unexpected reply"):
        type(REGISTRY["poetrydb"])(Client()).fetch("Emily Dickinson")


def test_poetrydb_miss_is_reported_as_no_poems(answer):
    answer(json.dumps({"status": 404, "reason": "Not found"}))
    with pytest.raises(SourceError, match="no poems for Emily Dickinson"):
        type(REGISTRY["poetrydb"])(Client()).fetch("Emily Dickinson")


def test_a_bug_in_parsing_wikitext_is_not_blamed_on_wikiquote(answer, monkeypatch):
    from hyprmuse.sources import wikiquote

    def broken(wikitext, title):
        raise IndexError("bug")

    monkeypatch.setattr(wikiquote, "parse_wikitext", broken)
    answer(json.dumps({"parse": {"wikitext": {"*": "* A quote."}}}))
    with pytest.raises(IndexError):
        wikiquote.Wikiquote(Client()).fetch("en:Somebody")
