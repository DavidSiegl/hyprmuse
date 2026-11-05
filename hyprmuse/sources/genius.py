"""Genius: song lyrics for any musical artist. Sliceable items."""

import statistics
import re

from ..text import mark_stanzas
from .base import Candidate, Client, Item, NotFound, SourceError, Subject, parse_html, reading

API = "https://genius.com/api"

# Most entries of an artist's song list one harvest reads, the most popular
# first; the artist's own songs among them are harvested. Without a bound, a
# wrong match with ~23,000 songs paged the song list for half an hour until
# Genius answered HTTP 403 and blocked the machine (#43). Songs the artist is
# only featured on count too, since listing them costs requests all the same.
# The largest artist in the author's library has 164 songs; 300 is 15 pages of 20.
MAX_SONGS = 300

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
    soup = parse_html(html)
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


def _own_songs(listed: list[dict], artist_id: str) -> tuple[dict, list[dict]]:
    """The artist's record and their own songs ({"title", "url"} each) among
    ``listed``, entries as ``Genius._song_page`` returns them, in their order.

    An entry whose primary artist is someone else is a guest appearance and is
    left out; one with no primary artist id is kept. The record is that of the
    first entry with the artist's id, {} when there is none.
    """
    artist: dict = {}
    songs = []
    for entry in listed:
        primary = entry["primary_artist"]
        if primary.get("id") and str(primary["id"]) != str(artist_id):
            continue
        if primary.get("id") and not artist:
            artist = {"name": primary.get("name", ""), "url": primary.get("url", "")}
        songs.append({"title": entry["title"], "url": entry["url"]})
    return artist, songs


class Genius:
    name = "genius"
    domain = "music"
    produces_atomic = False

    def __init__(self, client: Client):
        """``client`` makes every request this source sends."""
        self._client = client

    def search(self, query: str, lang: str = "en") -> list[Candidate]:
        api_url = f"{API}/search/artist"
        resp = self._client.get(api_url, params={"q": query})
        hits = []
        with reading(self.name, api_url):
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
        """The artist's own record and their songs among the MAX_SONGS most
        popular entries of their song list.

        The artist record ({"name", "url"}) is read off those songs, so it is
        empty when the artist is not the primary artist of any of them. When
        the limit cuts the list short, ``progress`` is told so.
        """
        listed: list[dict] = []
        page: int | None = 1
        while page and len(listed) < MAX_SONGS:
            if progress:
                progress(f"song list page {page} ({len(listed)} listed so far)")
            entries, page = self._song_page(artist_id, page)
            listed += entries
        if page or len(listed) > MAX_SONGS:
            listed = listed[:MAX_SONGS]
            if progress:
                progress(f"read only the {MAX_SONGS} most popular of more songs listed")
        return _own_songs(listed, artist_id)

    def _song_page(self, artist_id: str, page: int) -> tuple[list[dict], int | None]:
        """Page ``page`` (from 1) of the artist's song list, most popular first.

        Returns the page's entries, guest appearances included, each as
        {"title", "url", "primary_artist"} with Genius's primary_artist record
        ({} when an entry has no such key), and the number of the next page,
        None after the last one. Raises SourceError when the request fails or
        the reply is not shaped as expected, a primary_artist that is null or
        not an object included.
        """
        api_url = f"{API}/artists/{artist_id}/songs"
        resp = self._client.get(api_url, params={"page": page, "sort": "popularity"})
        with reading(self.name, api_url):
            response = resp.json().get("response", {})
            entries = []
            for song in response.get("songs", []):
                primary = song.get("primary_artist", {})
                if not isinstance(primary, dict):
                    raise TypeError(f"primary_artist is {primary!r}")
                entries.append({"title": song["title"], "url": song["url"],
                                "primary_artist": primary})
            return entries, response.get("next_page")

    def _lyrics(self, url: str) -> str | None:
        """The lyrics on the song page at ``url``; None when it has none.

        A song without a page (HTTP 404) has none. Any other failure raises
        SourceError, so a rate limit or an outage fails the whole harvest
        instead of silently leaving those songs out of it.
        """
        try:
            resp = self._client.get(url)
        except NotFound:
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
        if not subject.items:
            raise SourceError(f"no lyrics harvested for {name}")
        return subject


# Lyrics pages are scraped one after another, so the gap is long and jittered;
# it spaces the API calls the same way, as they go to the same host.
SOURCE = Genius(Client(gap=1.0, jitter=1.5))
