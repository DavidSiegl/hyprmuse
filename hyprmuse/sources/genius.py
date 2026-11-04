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


# Stands in for a <br> while the surrounding markup whitespace is collapsed.
_BREAK = "\x00"


def lyrics_text(html: str) -> str | None:
    """Flatten a Genius lyrics page to text, with <br> as the only line break.

    Genius wraps annotated phrases in inline <a> elements, so the element tree
    carries no line structure of its own: only <br> does, one per line and two
    per stanza break. Every other newline in the markup is layout whitespace.
    Treating those as breaks too - which joining the text nodes with a "\n"
    separator did - both split an annotated line in three and doubled every
    real break, so every line became its own stanza; since the selector slices
    within a stanza, no pick could ever be longer than a single line.
    """
    soup = BeautifulSoup(html, "lxml")
    containers = soup.find_all("div", attrs={"data-lyrics-container": "true"})
    if not containers:
        return None
    chunks = []
    for container in containers:
        for excluded in container.find_all(attrs={"data-exclude-from-selection": "true"}):
            excluded.decompose()
        for br in container.find_all("br"):
            br.replace_with(_BREAK)
        lines = [" ".join(part.split()) for part in container.get_text().split(_BREAK)]
        chunks.append("\n".join(lines).strip())
    return "\n\n".join(chunks).strip()


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
                    hint="artist",
                ))
        return hits

    def _songs(self, artist_id: str, progress=None) -> tuple[dict, list[dict]]:
        """The artist's own record and their songs, most popular first.

        The artist record ({"name", "url"}) is read off the songs, so it is
        empty when the artist is not the primary artist of any song.
        """
        artist: dict = {}
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
                primary = song.get("primary_artist", {})
                if primary.get("id") and str(primary["id"]) != str(artist_id):
                    continue
                if primary.get("id") and not artist:
                    artist = {"name": primary.get("name", ""),
                              "url": primary.get("url", "")}
                songs.append({"title": song["title"], "url": song["url"]})
            page = body.get("next_page")
        return artist, songs

    def _lyrics(self, url: str) -> str | None:
        try:
            resp = get(url, key="genius")
        except SourceError:
            return None
        return lyrics_text(resp.text)

    def fetch(self, source_id: str, progress=None) -> Subject:
        artist, songs = self._songs(source_id, progress)
        name = artist.get("name") or f"Genius artist {source_id}"
        url = artist.get("url", "")
        subject = Subject(
            source=self.name, source_id=source_id, name=name,
            domain=self.domain, url=url,
            attribution={"provider": "Genius", "url": url,
                         "note": "Lyrics scraped for personal offline use."},
        )
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
            raise SourceError(f"no lyrics harvested for {name}")
        return subject


SOURCE = Genius()
