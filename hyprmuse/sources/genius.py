"""Genius: song lyrics for any musical artist. Sliceable items."""

import random
import statistics
import re
import time

from bs4 import BeautifulSoup

from ..text import mark_stanzas
from .base import Candidate, Item, Source, SourceError, Subject, get

API = "https://genius.com/api"

# Boilerplate Genius injects into the lyrics container.
_HEADER_LYRICS = re.compile(r"\s+lyrics$", re.IGNORECASE)
_CONTRIBUTORS = re.compile(r"^\d*\s*contributors?\b", re.IGNORECASE)
_TRANSLATIONS = re.compile(r"^translations?$", re.IGNORECASE)
_EMBED = re.compile(r"^\d*\s*embed$", re.IGNORECASE)
_SECTION = re.compile(r"^\[.*\]$")
_ALSO_LIKE = re.compile(r"^you might also like", re.IGNORECASE)


def clean_lines(raw: str) -> list[str]:
    """Strip Genius boilerplate once, at harvest time.

    Anchored to line position and shape rather than substring-matched, so a
    genuine lyric containing a word like "lyrics" survives. Blank lines and
    [Section] markers both become a single blank line: the stanza break the
    selector slices within.
    """
    lines = [ln.strip() for ln in raw.split("\n")]

    # Drop the leading header block: contributor counts, "<Title> Lyrics",
    # translation lists and the About blurb that precedes the first section.
    start = 0
    for idx, line in enumerate(lines[:8]):
        if _CONTRIBUTORS.match(line) or _TRANSLATIONS.match(line) or _HEADER_LYRICS.search(line):
            start = idx + 1
    lines = lines[start:]

    # If the song is sectioned, real lyrics begin at the first [Section] marker;
    # anything before it is the description blurb.
    sectioned = False
    for idx, line in enumerate(lines):
        if _SECTION.match(line):
            lines, sectioned = lines[idx:], True
            break

    out = []
    for line in lines:
        if not line or _SECTION.match(line):
            out.append("")
        elif _EMBED.match(line) or _ALSO_LIKE.match(line) or _CONTRIBUTORS.match(line):
            continue
        else:
            out.append(line)

    out = mark_stanzas(out)
    if not sectioned:
        out = _strip_blurb(out)
    return out


def _strip_blurb(lines: list[str]) -> list[str]:
    """Drop a leading About blurb on songs that carry no [Section] markers.

    Without a section marker to anchor on there is no structural boundary, so
    fall back to shape: the blurb is prose - far longer than a sung line and
    ending in sentence punctuation - while lyric lines are short and mostly
    unpunctuated at the end.
    """
    while True:
        lines = mark_stanzas(lines)  # so lines[0] is the first real line
        body = [x for x in lines if x]
        if len(body) < 6:
            break
        head, rest = body[0], body[1:]
        median = statistics.median(len(x) for x in rest)
        if (len(head) >= 80 and head[-1] in ".!?"
                and len(head) >= 1.8 * max(median, 1)):
            lines = lines[1:]
            continue
        break
    return lines


class Genius:
    name = "genius"
    domain = "music"
    produces_atomic = False

    def search(self, query: str, lang: str = "en") -> list[Candidate]:
        resp = get(f"{API}/search/artist", params={"q": query}, key="genius", throttle=0.5)
        hits = []
        for section in resp.json().get("response", {}).get("sections", []):
            if section.get("type") != "artist":
                continue
            for hit in section.get("hits", []):
                res = hit.get("result", {})
                if not res.get("id"):
                    continue
                hits.append(Candidate(
                    source=self.name,
                    source_id=str(res["id"]),
                    name=res.get("name", query),
                    domain=self.domain,
                    lang=lang,
                    url=res.get("url", ""),
                    hint="artist",
                ))
        return hits

    def _songs(self, artist_id: str, progress=None) -> list[dict]:
        songs, page = [], 1
        while page:
            if progress:
                progress(f"song list page {page} ({len(songs)} so far)")
            resp = get(f"{API}/artists/{artist_id}/songs",
                       params={"page": page, "sort": "popularity"},
                       key="genius", throttle=0.5)
            body = resp.json().get("response", {})
            for song in body.get("songs", []):
                # Skip entries where this artist is only a featured guest.
                if song.get("primary_artist", {}).get("id") and \
                        str(song["primary_artist"]["id"]) != str(artist_id):
                    continue
                songs.append({"title": song["title"], "url": song["url"]})
            page = body.get("next_page")
        return songs

    def _lyrics(self, url: str) -> str | None:
        try:
            resp = get(url, key="genius")
        except SourceError:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        containers = soup.find_all("div", attrs={"data-lyrics-container": "true"})
        if not containers:
            return None
        chunks = []
        for container in containers:
            for excluded in container.find_all(attrs={"data-exclude-from-selection": "true"}):
                excluded.decompose()
            for br in container.find_all("br"):
                br.replace_with("\n")
            chunks.append(container.get_text(separator="\n").strip())
        return "\n\n".join(chunks).strip()

    def fetch(self, cand: Candidate, progress=None) -> Subject:
        subject = Subject(
            source=self.name, source_id=cand.source_id, name=cand.name,
            domain=self.domain, lang=cand.lang, url=cand.url,
            attribution={"provider": "Genius", "url": cand.url,
                         "note": "Lyrics scraped for personal offline use."},
        )
        songs = self._songs(cand.source_id, progress)
        for idx, song in enumerate(songs, 1):
            if progress:
                progress(f"[{idx}/{len(songs)}] {song['title']}")
            raw = self._lyrics(song["url"])
            if raw:
                lines = clean_lines(raw)
                if lines:
                    subject.items.append(Item(lines=lines, work=song["title"],
                                              url=song["url"], atomic=False))
            time.sleep(random.uniform(1.0, 2.5))
        if not subject.items:
            raise SourceError(f"no lyrics harvested for {cand.name}")
        return subject


SOURCE = Genius()
