"""Wikitext stripping and quote-bullet parsing."""

import pytest

from hyprmuse.sources import wikiquote as wq


@pytest.mark.parametrize("raw,expected", [
    ("[[Freedom]] is worth having", "Freedom is worth having"),
    ("[[w:Some Page|Displayed text]] follows", "Displayed text follows"),
    ("''italic'' and '''bold''' text", "italic and bold text"),
    ("A quote<ref>Book, 1920, p. 4</ref> ends", "A quote ends"),
    ("Before<!-- hidden note -->after", "Beforeafter"),
    ("Text {{template|arg}} more", "Text more"),
    ("See [http://example.org the source] here", "See the source here"),
    ("Bare [http://example.org] link", "Bare link"),
    ("Spaced&nbsp;out &amp; escaped", "Spaced out & escaped"),
    ("<span class='x'>tagged</span>", "tagged"),
    ("collapse    excess\n\nwhitespace", "collapse excess whitespace"),
])
def test_strip_markup(raw, expected):
    assert wq.strip_markup(raw) == expected


def test_strip_markup_handles_nested_templates():
    assert wq.strip_markup("a {{outer {{inner}} }} b").strip() == "a b"


@pytest.mark.parametrize("raw,quote,note", [
    ('"Ein Zitat" - Quelle 1978', "Ein Zitat", "Quelle 1978"),
    ('"Nur das Zitat"', "Nur das Zitat", ""),
    ("Plain quote with no quoting", "Plain quote with no quoting", ""),
    ('„Deutsche Zitatzeichen“ - Werk', "Deutsche Zitatzeichen", "Werk"),
])
def test_split_quote_and_note(raw, quote, note):
    assert wq._split_quote_and_note(raw) == (quote, note)


WIKITEXT = """
== Zitate mit Quellenangabe ==
* "Ein hinreichend langes Zitat mit Quelle" - ''Ein Werk, 1959''
* "Ein zweites Zitat das lang genug ist"
* kurz

== Zitate über die Person ==
* "Dieses Zitat stammt von jemand anderem und zaehlt nicht"

== Weblinks ==
* [http://example.org Eine Seite]
"""


def test_parse_wikitext_extracts_quotes_and_notes():
    items = wq.parse_wikitext(WIKITEXT)
    assert [i.lines[0] for i in items] == [
        "Ein hinreichend langes Zitat mit Quelle",
        "Ein zweites Zitat das lang genug ist",
    ]
    assert items[0].note == "Ein Werk, 1959"
    assert items[1].note == ""


def test_parse_wikitext_skips_about_and_link_sections():
    texts = [i.lines[0] for i in wq.parse_wikitext(WIKITEXT)]
    assert not any("jemand anderem" in t for t in texts)
    assert not any("Eine Seite" in t for t in texts)


def test_parse_wikitext_marks_items_atomic():
    assert all(i.atomic for i in wq.parse_wikitext(WIKITEXT))


def test_parse_wikitext_drops_too_short_and_too_long():
    text = "== Quotes ==\n* tiny\n* " + "x" * 500 + "\n* " + "y" * 50
    items = wq.parse_wikitext(text)
    assert len(items) == 1
    assert items[0].lines[0] == "y" * 50


def test_sub_bullet_becomes_note_of_preceding_quote():
    text = ("== Quotes ==\n"
            "* A quote long enough to survive the filter\n"
            "** ''The Book'', 1925\n")
    items = wq.parse_wikitext(text)
    assert items[0].note == "The Book, 1925"


def test_english_about_heading_is_skipped():
    text = ("== Quotes about him ==\n"
            "* Something said by another person entirely\n")
    assert wq.parse_wikitext(text) == []


def parse_source(fake_client, fake_response, lang, title, payload):
    """A Wikiquote whose ``lang`` edition answers a parse of ``title``."""
    url = fake_client.url(f"https://{lang}.wikiquote.org/w/api.php", {
        "action": "parse", "page": title, "prop": "wikitext", "format": "json"})
    return wq.Wikiquote(fake_client({url: fake_response(payload)}))


def test_fetch_raises_on_api_error(fake_client, fake_response):
    from hyprmuse.sources.base import SourceError
    src = parse_source(fake_client, fake_response, "en", "Nobody",
                       {"error": {"info": "page not found"}})
    with pytest.raises(SourceError, match="page not found"):
        src.fetch("en:Nobody")


def test_fetch_builds_subject_with_licence(fake_client, fake_response):
    subject = parse_source(fake_client, fake_response, "de", "Jemand",
                           {"parse": {"wikitext": {"*": WIKITEXT}}}).fetch("de:Jemand")
    assert subject.name == "Jemand"
    assert subject.lang == "de"
    assert subject.url == "https://de.wikiquote.org/wiki/Jemand"
    assert len(subject.items) == 2
    assert subject.attribution["license"] == "CC BY-SA 4.0"


def test_search_ids_carry_the_edition(fake_client, fake_response):
    url = fake_client.url("https://de.wikiquote.org/w/api.php", {
        "action": "query", "list": "search", "srsearch": "kafka",
        "format": "json", "srlimit": 8})
    client = fake_client({url: fake_response({"query": {"search": [
        {"title": "Franz Kafka", "wordcount": 1200}]}})})
    hits = wq.Wikiquote(client).search("kafka", "de")
    assert [(h.source_id, h.hint) for h in hits] == [("de:Franz Kafka", "1200 words")]
