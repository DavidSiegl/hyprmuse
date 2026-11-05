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
    "keys": json.dumps({"response": {"songs": [{}], "sections": [{"type": "artist", "hits": [5]}]}, "query": {"search": [{}]},
                        "parse": {}, "authors": 5}),
}


@pytest.fixture
def answer(monkeypatch):
    """Make every request get HTTP 200 with the body passed in."""
    def answer_with(body):
        class Response:
            status_code = 200
            text = body
            encoding = "utf-8"

            def json(self):
                return json.loads(body)

        monkeypatch.setattr(base.requests, "get", lambda *_, **__: Response())
    return answer_with


@pytest.mark.parametrize("body", sorted(BODIES))
@pytest.mark.parametrize("name", sorted(JSON_SOURCES))
@pytest.mark.parametrize("call", ["search", "fetch"])
def test_unexpected_reply_is_a_source_error(answer, name, body, call):
    answer(BODIES[body])
    src = type(REGISTRY[name])(Client())
    with pytest.raises(SourceError):
        if call == "search":
            src.search("anything", "en")
        else:
            src.fetch(JSON_SOURCES[name])
