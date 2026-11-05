"""Wikiquote: quotations for authors, thinkers, films and more. Atomic items."""

import re

from .base import Candidate, Item, Source, SourceError, Subject, get

# Headings of sections that hold words other than the subject's own: quotes
# about them, quotes wrongly attributed to them, bibliography and links. Each
# alternative must match the start of the heading's plain text, ignoring case;
# grouped by edition. A section "about" the subject named by a bare preposition
# is recognised by _ABOUT instead, since that preposition also heads sections
# of the subject's own words on a topic.
_NOT_THEIR_WORDS = re.compile(r"""^(?:
    quotes?\s+about | misattributed | references?\b | external\s+links | see\s+also
    | sources?\b | notes?\b | bibliogra[fp] | further\s+reading                     # en
    | zitate\s+über | fälschlich | weblinks | literatur | quellen | einzelnachweise
    | siehe\s+auch | anmerkungen | nachweise                                        # de
    | citations\s+(?:sur|le\s+concernant|la\s+concernant) | attribuées\s+à\s+tort
    | voir\s+aussi | liens\s+externes | références                                  # fr
    | citas\s+sobre | atribuidas\s+(?:erróneamente|falsamente) | véase\s+también
    | enlaces\s+externos | referencias | fuentes                                    # es
    | citazioni\s+su | errate | fonti | voci\s+correlate | altri\s+progetti
    | opere\b                                                                       # it
    | citações\s+sobre | sobre$ | mal\s+atribuídas | atribuições\s+errôneas
    | ver\s+também | ligações\s+externas | referências                              # pt
    | cytaty\s+błędnie | zobacz\s+też | linki\s+zewnętrzne | przypisy               # pl
    | ошибочно | см\.\s+также | примечания | ссылки | литература                    # ru
    | citaten\s+over | ten\s+onrechte | zie\s+ook | externe\s+links | bronnen      # nl
)""", re.IGNORECASE | re.VERBOSE)

# "About <someone or something>", per edition. Such a section is about the
# subject only when what follows names them (see _names_subject).
_ABOUT = re.compile(
    r"^(?:about|über|sur|à\s+propos\s+d[e']|sobre|su|sull[ao']|o|об?|обо|over)\s+(.+)",
    re.IGNORECASE)

# Pronouns that stand for the subject after one of _ABOUT's prepositions.
_PRONOUNS = frozenset({"him", "her", "ihn", "sie", "lui", "elle", "él", "ella", "lei",
                       "nim", "niej", "нём", "нем", "ней", "hem", "haar"})

# Quote templates, by lowercased name: the parameter holding the quote, and
# the one holding its source ("" when the template has none). fr writes
# {{Citation|…}}, ru {{Q|…|Автор=…}}, nl {{Citaat|tekst=…|bron=…}}.
_QUOTE_TEMPLATES = {
    "citation": ("citation", ""),
    "q": ("1", "автор"),
    "citaat": ("tekst", "bron"),
}
_QUOTE_TEMPLATE = re.compile(
    r"\s*\{\{\s*(" + "|".join(_QUOTE_TEMPLATES) + r")\s*(?:\||$)", re.IGNORECASE)

# Quotation marks a quote may open with, and the marks that close each:
# "…" and “…” (en), „…“ (de) or „…” (pl), «…» (es, fr, pt, ru), ‹…›.
_QUOTE_MARKS = {'"': '"', "„": "“”", "“": "”", "«": "»", "‹": "›"}

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
    """Separate a quote in quotation marks from the source written after it.

    «quote» – source, "quote" - source and the like give (quote, source);
    text that does not open with a quotation mark of _QUOTE_MARKS, or never
    closes it, is all quote and gives (text, "").
    """
    text = text.strip()
    opening = text[:1]
    closing = _QUOTE_MARKS.get(opening)
    if not closing:
        return text, ""
    depth = 0  # marks of the same kind nested inside the quote
    for i, ch in enumerate(text[1:], 1):
        if ch in closing:
            if depth == 0:
                return text[1:i].strip(), _note(text[i + 1:])
            depth -= 1
        elif ch == opening:
            depth += 1
    return text, ""


def _note(text: str) -> str:
    """A source as written after a quote, without the dash or comma joining them."""
    return text.strip().lstrip(".,;:-–— ").strip()


def _names_subject(words: str, title: str) -> bool:
    """Whether ``words``, following "about", name the subject of page ``title``.

    Names inflect (ru "Об Эйнштейне", pl "O Albercie Einsteinie"), so a word
    names the subject when its first four letters are those of a word of
    four letters or more in the title; a pronoun of _PRONOUNS does too.
    """
    stems = {w[:4] for w in re.findall(r"\w+", title.casefold()) if len(w) >= 4}
    return any(w in _PRONOUNS or (len(w) >= 4 and w[:4] in stems)
               for w in re.findall(r"\w+", words.casefold()))


def _holds_their_words(heading: str, title: str) -> bool:
    """Whether a section headed ``heading`` holds the subject's own words."""
    text = strip_markup(heading)
    if _NOT_THEIR_WORDS.match(text):
        return False
    about = _ABOUT.match(text)
    return not (about and _names_subject(about.group(1), title))


def _template_end(wikitext: str, start: int) -> int:
    """The index just past the template opening at ``start``.

    The text's length when the template never closes.
    """
    depth = 0
    i = start
    while i < len(wikitext) - 1:
        pair = wikitext[i:i + 2]
        if pair == "{{":
            depth += 1
            i += 2
        elif pair == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return i
        else:
            i += 1
    return len(wikitext)


def _template_params(call: str) -> dict[str, str]:
    """The parameters of the template call ``call`` (``{{name|…}}``, maybe unclosed).

    Positional parameters are keyed "1", "2", …, named ones by their name in
    lower case; as in MediaWiki, a parameter with "=" outside nested links and
    templates is named. Values are raw wikitext, stripped of outer whitespace.
    """
    body = call[2:-2] if call.endswith("}}") else call[2:]
    parts, depth, begin = [], 0, 0
    i = 0
    while i < len(body):
        pair = body[i:i + 2]
        if pair in ("{{", "[["):
            depth += 1
            i += 2
        elif pair in ("}}", "]]"):
            depth -= 1
            i += 2
        else:
            if body[i] == "|" and depth == 0:
                parts.append(body[begin:i])
                begin = i + 1
            i += 1
    parts.append(body[begin:])
    params: dict[str, str] = {}
    position = 0
    for part in parts[1:]:  # parts[0] is the template's name
        name, eq, text = part.partition("=")
        if eq and "{{" not in name and "[[" not in name:
            params[name.strip().casefold()] = text.strip()
        else:
            position += 1
            params[str(position)] = part.strip()
    return params


def _quote_item(text: str, note: str) -> Item | None:
    """An item for a quote of plain text, or None if it is too short or long to show."""
    if not 15 <= len(text) <= 400:
        return None
    return Item(lines=[text], atomic=True, note=note)


def parse_wikitext(wikitext: str, title: str) -> list[Item]:
    """The subject's own quotes on Wikiquote page ``title``, in page order.

    ``wikitext`` is the page's source. Quotes are read from "*" bullets, with
    a "**" sub-bullet or the text after a closing quotation mark as the
    source, and from the quote templates of _QUOTE_TEMPLATES. Sections, and
    every section nested in them, are skipped when their heading marks words
    other than the subject's (_NOT_THEIR_WORDS, or "about" + the subject's
    name, which ``title`` gives). Quotes under 15 or over 400 characters are
    left out. Each item is atomic and has one line.
    """
    items: list[Item] = []
    skip_level = 0  # level of the heading whose section is skipped; 0 when none
    pos = 0
    while pos < len(wikitext):
        eol = wikitext.find("\n", pos)
        eol = len(wikitext) if eol < 0 else eol
        line = wikitext[pos:eol]
        nxt = eol + 1

        heading = _HEADING.match(line)
        template = _QUOTE_TEMPLATE.match(line)
        if heading:
            level = len(heading.group(1))
            if not skip_level or level <= skip_level:
                skip_level = 0 if _holds_their_words(heading.group(2), title) else level
        elif template:
            # A template may span lines; read it whole, then go on after it.
            start = pos + line.index("{{")
            nxt = _template_end(wikitext, start)
            if not skip_level:
                _read_template(wikitext[start:nxt], template.group(1), items)
        elif not skip_level:
            _read_bullet(line.strip(), items)
        pos = nxt
    return items


def _read_template(call: str, name: str, items: list[Item]) -> None:
    """Add the quote of ``call``, a call of quote template ``name``, to ``items``."""
    quote_param, note_param = _QUOTE_TEMPLATES[name.casefold()]
    params = _template_params(call)
    quote = strip_markup(params.get(quote_param) or params.get("1", ""))
    item = _quote_item(quote, _note(strip_markup(params.get(note_param, ""))))
    if item:
        items.append(item)


def _read_bullet(line: str, items: list[Item]) -> None:
    """Add the quote of a "*" bullet to ``items``, or a "**" source to its last item."""
    # '**' sub-bullets are the citation for the quote above them.
    if line.startswith("**"):
        if items and not items[-1].note:
            note = strip_markup(line.lstrip("*").strip())
            if note:
                items[-1].note = note
        return
    if not line.startswith("*"):
        return
    body = strip_markup(line.lstrip("*").strip())
    if body:
        item = _quote_item(*_split_quote_and_note(body))
        if item:
            items.append(item)


class Wikiquote:
    name = "wikiquote"
    domain = "quotations"
    produces_atomic = True

    def _api(self, lang: str) -> str:
        return f"https://{lang}.wikiquote.org/w/api.php"

    def search(self, query: str, lang: str = "en") -> list[Candidate]:
        resp = get(self._api(lang), params={
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": 8,
        }, key="wikiquote", throttle=0.2)
        out = []
        for hit in resp.json().get("query", {}).get("search", []):
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
        resp = get(self._api(lang), params={
            "action": "parse", "page": title, "prop": "wikitext", "format": "json",
        }, key="wikiquote", throttle=0.2)
        data = resp.json()
        if "error" in data:
            raise SourceError(f"wikiquote: {data['error'].get('info', 'page not found')}")
        items = parse_wikitext(data["parse"]["wikitext"]["*"], title)
        if not items:
            raise SourceError(f"no quotes parsed from {title}")
        return Subject(
            source=self.name, source_id=source_id, name=title,
            domain=self.domain, lang=lang, url=url, items=items,
            attribution={"provider": "Wikiquote", "url": url,
                         "license": "CC BY-SA 4.0"},
        )


SOURCE = Wikiquote()
