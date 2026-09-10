"""PoetryDB: public-domain poetry. Sliceable items (a window of verse lines)."""

import difflib

from ..text import mark_stanzas
from .base import Candidate, Item, Source, SourceError, Subject, get

API = "https://poetrydb.org"


class PoetryDB:
    name = "poetrydb"
    domain = "poetry"
    produces_atomic = False

    def _authors(self) -> list[str]:
        return get(f"{API}/author", key="poetrydb", throttle=0.2).json().get("authors", [])

    def search(self, query: str, lang: str = "en") -> list[Candidate]:
        authors = self._authors()
        low = query.lower()
        exact = [a for a in authors if low in a.lower()]
        # Fall back to fuzzy matching so "dickinson" or a typo still resolves.
        ranked = exact or difflib.get_close_matches(query, authors, n=5, cutoff=0.5)
        return [
            Candidate(source=self.name, source_id=a, name=a, domain=self.domain,
                      lang="en", url=f"{API}/author/{a.replace(' ', '%20')}",
                      hint="public domain")
            for a in ranked[:8]
        ]

    def fetch(self, cand: Candidate, progress=None) -> Subject:
        if progress:
            progress(f"fetching poems by {cand.name}")
        resp = get(f"{API}/author/{cand.source_id}/title,author,lines",
                   key="poetrydb", throttle=0.2)
        poems = resp.json()
        if isinstance(poems, dict):  # PoetryDB reports misses as {"status":404,...}
            raise SourceError(f"poetrydb: no poems for {cand.name}")
        items = []
        for poem in poems:
            lines = mark_stanzas(poem.get("lines", []))  # blanks = stanza breaks
            if lines:
                items.append(Item(lines=lines, work=poem.get("title", ""),
                                  url=cand.url, atomic=False))
        if not items:
            raise SourceError(f"poetrydb: no usable poems for {cand.name}")
        return Subject(
            source=self.name, source_id=cand.source_id, name=cand.name,
            domain=self.domain, lang="en", url=cand.url, items=items,
            attribution={"provider": "PoetryDB", "url": API, "license": "public domain"},
        )


SOURCE = PoetryDB()
