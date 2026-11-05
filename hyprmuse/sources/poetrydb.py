"""PoetryDB: public-domain poetry. Sliceable items (a window of verse lines)."""

import difflib

from ..text import mark_stanzas
from .base import Candidate, Client, Item, SourceError, Subject, reading

API = "https://poetrydb.org"


def _strings(value) -> list[str]:
    """``value``, which a reply says is a list of strings; TypeError if it is not."""
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise TypeError(f"expected a list of strings, got {value!r:.60}")
    return value


class PoetryDB:
    name = "poetrydb"
    domain = "poetry"
    produces_atomic = False

    def __init__(self, client: Client):
        """``client`` makes every request this source sends."""
        self._client = client

    def _authors(self) -> list[str]:
        api_url = f"{API}/author"
        resp = self._client.get(api_url)
        with reading(self.name, api_url):
            return _strings(resp.json().get("authors", []))

    def search(self, query: str, lang: str = "en") -> list[Candidate]:
        authors = self._authors()
        low = query.lower()
        exact = [a for a in authors if low in a.lower()]
        # Fall back to fuzzy matching so "dickinson" or a typo still resolves.
        ranked = exact or difflib.get_close_matches(query, authors, n=5, cutoff=0.5)
        return [
            Candidate(source=self.name, source_id=a, name=a, domain=self.domain,
                      hint="public domain")
            for a in ranked[:8]
        ]

    def fetch(self, source_id: str, progress=None) -> Subject:
        # PoetryDB keys poets by their full name, so the id is the name.
        name = source_id
        url = f"{API}/author/{name.replace(' ', '%20')}"
        if progress:
            progress(f"fetching poems by {name}")
        api_url = f"{API}/author/{source_id}/title,author,lines"
        resp = self._client.get(api_url)
        with reading(self.name, api_url):
            reply = resp.json()
            # PoetryDB answers a miss with HTTP 200 and {"status": 404, ...}.
            if isinstance(reply, dict) and reply.get("status") == 404:
                raise SourceError(f"poetrydb: no poems for {name}")
            if not isinstance(reply, list):
                raise TypeError(f"poems are {type(reply).__name__}")
            poems = []
            for poem in reply:
                title = poem.get("title", "")
                if not isinstance(title, str):
                    raise TypeError(f"title is {type(title).__name__}")
                poems.append((title, _strings(poem.get("lines", []))))
        items = []
        for title, raw in poems:
            lines = mark_stanzas(raw)  # blanks = stanza breaks
            if lines:
                items.append(Item(lines=lines, work=title, url=url, atomic=False))
        if not items:
            raise SourceError(f"poetrydb: no usable poems for {name}")
        return Subject(
            source=self.name, source_id=source_id, name=name,
            domain=self.domain, lang="en", url=url, items=items,
            attribution={"provider": "PoetryDB", "url": API, "license": "public domain"},
        )


SOURCE = PoetryDB(Client(gap=0.2))
