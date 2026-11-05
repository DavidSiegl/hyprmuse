"""Passage and header extraction from a Gutenberg plaintext."""

import pytest

from hyprmuse.sources import gutenberg
from hyprmuse.sources.base import SourceError
from hyprmuse.sources.gutenberg import extract_passages, read_header

BOOK = """
The Project Gutenberg eBook of Something

*** START OF THE PROJECT GUTENBERG EBOOK SOMETHING ***

CHAPTER ONE

The room was colder than he had expected, and the window would not close
properly against the wind. He stood there for a long while and considered
what the morning might bring.

A short bit.

She replied that the arrangement had never been agreeable to anyone
concerned, least of all to herself, and that she intended to say so plainly.

*** END OF THE PROJECT GUTENBERG EBOOK SOMETHING ***

This eBook is for the use of anyone anywhere at no cost and with almost
no restrictions whatsoever under the terms of the license included.
"""


def test_licence_wrapper_is_stripped():
    joined = " ".join(extract_passages(BOOK))
    assert "PROJECT GUTENBERG" not in joined
    assert "no restrictions whatsoever" not in joined


def test_extracts_prose_sentences():
    passages = extract_passages(BOOK)
    assert passages
    assert any(p.startswith("The room was colder") for p in passages)
    assert any(p.startswith("She replied") for p in passages)


def test_rejects_short_fragments_and_headings():
    passages = extract_passages(BOOK)
    assert all(60 <= len(p) <= 300 for p in passages)
    assert "CHAPTER ONE" not in passages
    assert "A short bit." not in passages


def test_all_passages_start_with_a_capital():
    assert all(p[0].isupper() for p in extract_passages(BOOK))


def test_limit_caps_the_sample():
    body = " ".join(
        f"This is sentence number {i} and it is comfortably long enough to "
        f"pass the minimum length filter used by the extractor." for i in range(50))
    text = f"*** START OF THE PROJECT GUTENBERG EBOOK X ***\n\n{body}\n"
    assert len(extract_passages(text, limit=5)) == 5


def test_missing_markers_still_yields_passages():
    """Some editions lack the START/END banners entirely."""
    text = ("He had walked the same road every morning for thirty years and "
            "never once thought to ask where it went.")
    assert extract_passages(text) == [text]


def test_dangling_quote_is_rejected():
    text = ('*** START OF THE PROJECT GUTENBERG EBOOK X ***\n\n'
            'He said "this sentence has only one quotation mark in it and so '
            'should be dropped by the extractor.\n')
    assert extract_passages(text) == []


def test_header_fields_come_from_the_preamble_only():
    text = ("Title: Die Verwandlung\n\nAuthor: Franz Kafka\nLanguage: German\n\n"
            "*** START OF THE PROJECT GUTENBERG EBOOK X ***\n\n"
            "Title: a line inside the book that only looks like a field\n")
    assert read_header(text) == {"title": "Die Verwandlung",
                                 "author": "Franz Kafka", "language": "German"}


def test_header_without_fields_is_empty():
    assert read_header(BOOK) == {}


TEXT_URLS = [f"{gutenberg.BASE}/cache/epub/7/pg7.txt",
             f"{gutenberg.BASE}/files/7/7-0.txt",
             f"{gutenberg.BASE}/ebooks/7.txt.utf-8"]


def test_fetch_falls_back_to_the_third_url(fake_client, fake_response):
    """The first URL fails outright and the second holds no passages."""
    client = fake_client({TEXT_URLS[1]: fake_response(text="Title: Empty\n"),
                          TEXT_URLS[2]: fake_response(text=BOOK)})
    subject = gutenberg.Gutenberg(client).fetch("7")
    assert client.requested == TEXT_URLS
    assert any(i.lines[0].startswith("The room was colder") for i in subject.items)


def test_fetch_stops_at_the_first_url_that_yields_passages(fake_client, fake_response):
    client = fake_client({TEXT_URLS[0]: fake_response(text=BOOK)})
    gutenberg.Gutenberg(client).fetch("7")
    assert client.requested == TEXT_URLS[:1]


def test_fetch_fails_when_no_url_yields_the_book(fake_client):
    with pytest.raises(SourceError, match="could not retrieve ebook 7"):
        gutenberg.Gutenberg(fake_client({})).fetch("7")


SEARCH_PAGE = """<ul>
<li class="booklink"><a class="link" href="/ebooks/22367">
  <span class="title">Die Verwandlung</span><span class="subtitle">Franz Kafka</span></a></li>
<li class="booklink"><a class="link" href="/ebooks/search/?sort_order=release_date">
  <span class="title">Sort by release date</span></a></li>
</ul>"""


def test_search_reads_book_links_and_skips_other_links(fake_client, fake_response):
    url = fake_client.url(f"{gutenberg.BASE}/ebooks/search/", {"query": "kafka"})
    hits = gutenberg.Gutenberg(fake_client({url: fake_response(text=SEARCH_PAGE)})).search("kafka")
    assert [(h.source_id, h.name, h.hint) for h in hits] == [
        ("22367", "Die Verwandlung", "Franz Kafka")]
