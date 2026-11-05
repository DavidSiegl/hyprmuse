"""Wikiquote: quotations for authors, thinkers, films and more. Atomic items."""

import re

from .base import Candidate, Client, Item, SourceError, Subject, hyprmuse_user_agent, reading

# Sections holding quotes *about* the subject, or bare bibliography, rather
# than words by them. Matched against the heading text, per language.
_SKIP_SECTIONS = re.compile(
    r"^\s*(zitate\s+über|über\s+|quotes?\s+about|about\s+|references?|external\s+links|"
    r"see\s+also|weblinks|literatur|quellen|einzelnachweise|siehe\s+auch|"
    r"bibliograph|anmerkungen|nachweise)",
    re.IGNORECASE,
)

_REF = re.compile(r"<ref[^>]*?/>|<ref[^>]*?>.*?</ref>", re.DOTALL | re.IGNORECASE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_WIKILINK_PIPED = re.compile(r"\[\[[^\]|]*\|([^\]]*)\]\]")
_WIKILINK = re.compile(r"\[\[([^\]]*)\]\]")
_EXTLINK = re.compile(r"\[https?://\S+\s+([^\]]*)\]")
_EXTLINK_BARE = re.compile(r"\[https?://\S+\]")
_BOLD_ITALIC = re.compile(r"'{2,5}")
_HEADING = re.compile(r"^\s*(={2,6})\s*(.*?)\s*=*\s*$")


def strip_markup(text: str) -> str:
    """Reduce MediaWiki markup to plain readable text."""
    text = _COMMENT.sub("", text)
    text = _REF.sub("", text)
    for _ in range(3):  # nested templates
        new = _TEMPLATE.sub("", text)
        if new == text:
            break
        text = new
    text = _EXTLINK.sub(r"\1", text)
    text = _EXTLINK_BARE.sub("", text)
    text = _WIKILINK_PIPED.sub(r"\1", text)
    text = _WIKILINK.sub(r"\1", text)
    text = _BOLD_ITALIC.sub("", text)
    text = _TAG.sub("", text)
    text = text.replace("&nbsp;", " ").replace("&quot;", '"').replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


def _split_quote_and_note(text: str) -> tuple[str, str]:
    """German Wikiquote writes: "quote" - source. Separate the two."""
    text = text.strip()
    if text.startswith(('"', "„", "“")):
        closing = {'"': '"', "„": "“", "“": "”"}[text[0]]
        end = text.find(closing, 1)
        if end > 0:
            quote = text[1:end].strip()
            note = text[end + 1:].strip().lstrip("-–— ").strip()
            return quote, note
    return text, ""


def parse_wikitext(wikitext: str) -> list[Item]:
    """Pull quote bullets out of a Wikiquote page, skipping 'about' sections."""
    items: list[Item] = []
    skipping = False
    for raw_line in wikitext.split("\n"):
        heading = _HEADING.match(raw_line)
        if heading:
            skipping = bool(_SKIP_SECTIONS.match(heading.group(2)))
            continue
        if skipping:
            continue

        stripped = raw_line.strip()
        # '**' sub-bullets are the citation for the quote above them.
        if stripped.startswith("**"):
            if items and not items[-1].note:
                note = strip_markup(stripped.lstrip("*").strip())
                if note:
                    items[-1].note = note
            continue
        if not stripped.startswith("*"):
            continue

        body = strip_markup(stripped.lstrip("*").strip())
        if not body:
            continue
        quote, note = _split_quote_and_note(body)
        if len(quote) < 15 or len(quote) > 400:
            continue
        items.append(Item(lines=[quote], atomic=True, note=note))
    return items


class Wikiquote:
    name = "wikiquote"
    domain = "quotations"
    produces_atomic = True

    def __init__(self, client: Client):
        """``client`` makes every request this source sends."""
        self._client = client

    def _api(self, lang: str) -> str:
        return f"https://{lang}.wikiquote.org/w/api.php"

    def search(self, query: str, lang: str = "en") -> list[Candidate]:
        api = self._api(lang)
        body = self._client.json(api, params={
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": 8,
        })
        out = []
        with reading(self.name, api):
            for hit in body.get("query", {}).get("search", []):
                title = hit["title"]
                out.append(Candidate(
                    source=self.name, source_id=f"{lang}:{title}", name=title,
                    domain=self.domain, hint=f"{hit.get('wordcount', 0)} words",
                ))
        return out

    def fetch(self, source_id: str, progress=None) -> Subject:
        # The id is "<edition>:<page title>", so it carries the language too.
        lang, _, title = source_id.partition(":")
        url = f"https://{lang}.wikiquote.org/wiki/{title.replace(' ', '_')}"
        if progress:
            progress(f"parsing {title} ({lang}.wikiquote.org)")
        api = self._api(lang)
        reply = self._client.json(api, params={
            "action": "parse", "page": title, "prop": "wikitext", "format": "json",
        })
        with reading(self.name, api):
            if "error" in reply:
                raise SourceError(f"wikiquote: {reply['error'].get('info', 'page not found')}")
            items = parse_wikitext(reply["parse"]["wikitext"]["*"])
        if not items:
            raise SourceError(f"no quotes parsed from {title}")
        return Subject(
            source=self.name, source_id=source_id, name=title,
            domain=self.domain, lang=lang, url=url, items=items,
            attribution={"provider": "Wikiquote", "url": url,
                         "license": "CC BY-SA 4.0"},
        )


# Wikimedia asks bots to identify themselves; see hyprmuse_user_agent.
SOURCE = Wikiquote(Client(gap=0.2, user_agent=hyprmuse_user_agent()))
