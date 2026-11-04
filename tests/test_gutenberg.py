"""Passage and header extraction from a Gutenberg plaintext."""

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
