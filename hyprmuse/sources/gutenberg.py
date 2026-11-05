"""Project Gutenberg: passages from public-domain books. Atomic items.

Talks to gutenberg.org directly - the usual gutendex.com JSON wrapper is not
reliably reachable, so this scrapes the search page and reads the plaintext
cache endpoint instead.
"""

import random
import re

from .base import Candidate, Client, Item, SourceError, Subject, parse_html

BASE = "https://www.gutenberg.org"
MAX_PASSAGES = 300  # per book, keeps the stored file small and varied

_START = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*",
                    re.IGNORECASE | re.DOTALL)
_END = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*",
                  re.IGNORECASE | re.DOTALL)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_ALLCAPS = re.compile(r"^[^a-z]{8,}$")


_HEADER_FIELD = re.compile(r"^(Title|Author|Language):[ \t]*(.+?)\s*$", re.MULTILINE)

# Gutenberg names languages in English; only the common ones get a code; the
# rest are stored as "en", which only affects what `hyprmuse list` shows.
_LANG_CODES = {"English": "en", "German": "de", "French": "fr", "Spanish": "es",
               "Italian": "it", "Dutch": "nl", "Portuguese": "pt"}


def read_header(text: str) -> dict[str, str]:
    """The ebook's catalogue fields from its plaintext preamble.

    Returns lower-cased keys "title", "author" and "language", each present
    only if the preamble before the START banner names it. A field continued
    on further lines (a long title) keeps only its first line.
    """
    if m := _START.search(text):
        text = text[:m.start()]
    return {k.lower(): v for k, v in _HEADER_FIELD.findall(text)}


def extract_passages(text: str, limit: int = MAX_PASSAGES) -> list[str]:
    """Strip the Gutenberg licence wrapper, then sample readable sentences."""
    if m := _START.search(text):
        text = text[m.end():]
    if m := _END.search(text):
        text = text[:m.start()]

    # Paragraphs are blank-line separated; rejoin their internal hard wraps.
    paragraphs = re.split(r"\n\s*\n", text)
    candidates = []
    for para in paragraphs:
        flat = re.sub(r"\s+", " ", para).strip()
        if len(flat) < 60 or _ALLCAPS.match(flat):
            continue  # chapter headings, front matter, transcriber notes
        if flat.startswith(("Produced by", "Transcribed", "[Illustration")):
            continue
        for sentence in _SENTENCE.split(flat):
            sentence = sentence.strip()
            if not (60 <= len(sentence) <= 300):
                continue
            if not sentence[0].isupper() or "_" in sentence:
                continue
            if sentence.count('"') % 2:  # dangling quote from a split dialogue
                continue
            candidates.append(sentence)

    if len(candidates) > limit:
        candidates = random.sample(candidates, limit)
    return candidates


class Gutenberg:
    name = "gutenberg"
    domain = "prose"
    produces_atomic = True

    def __init__(self, client: Client):
        """``client`` makes every request this source sends."""
        self._client = client

    def search(self, query: str, lang: str = "en") -> list[Candidate]:
        resp = self._client.get(f"{BASE}/ebooks/search/", params={"query": query})
        soup = parse_html(resp.text)
        out = []
        for link in soup.select("li.booklink a.link"):
            href = link.get("href", "")
            m = re.match(r"^/ebooks/(\d+)$", href)
            if not m:
                continue
            title = link.select_one(".title")
            author = link.select_one(".subtitle")
            out.append(Candidate(
                source=self.name, source_id=m.group(1),
                name=(title.get_text(strip=True) if title else query),
                domain=self.domain,
                hint=author.get_text(strip=True) if author else "",
            ))
            if len(out) >= 8:
                break
        return out

    def fetch(self, source_id: str, progress=None) -> Subject:
        # The subject is the author and each passage's work is the book, both
        # read from the ebook's own header so a re-harvest needs only the id.
        book_id = source_id
        url = f"{BASE}/ebooks/{book_id}"
        if progress:
            progress(f"downloading ebook {book_id}")
        last_err = None
        for txt_url in (f"{BASE}/cache/epub/{book_id}/pg{book_id}.txt",
                        f"{BASE}/files/{book_id}/{book_id}-0.txt",
                        f"{BASE}/ebooks/{book_id}.txt.utf-8"):
            try:
                resp = self._client.get(txt_url)
            except SourceError as exc:
                last_err = exc
                continue
            resp.encoding = resp.encoding or "utf-8"
            if progress:
                progress("extracting passages")
            passages = extract_passages(resp.text)
            if not passages:
                continue
            meta = read_header(resp.text)
            title = meta.get("title", "")
            return Subject(
                source=self.name, source_id=book_id,
                name=meta.get("author") or title or f"Gutenberg ebook {book_id}",
                domain=self.domain,
                lang=_LANG_CODES.get(meta.get("language", ""), "en"),
                url=url,
                items=[Item(lines=[p], work=title, url=url, atomic=True)
                       for p in passages],
                attribution={"provider": "Project Gutenberg", "url": url,
                             "license": "public domain"},
            )
        raise SourceError(f"could not retrieve ebook {book_id}: {last_err}")


SOURCE = Gutenberg(Client(gap=1.0))
