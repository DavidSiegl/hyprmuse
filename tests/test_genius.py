"""The Genius boilerplate cleaner - the part with a real bug history."""

from hyprmuse.sources.genius import clean_lines

SONG_LINES = [
    "The morning bus is always late",
    "I count the stations one by one",
    "Nobody waves from the platform",
    "And the rain keeps its own time",
]
# The same song once sectioned: the [Refrain] marker becomes a stanza break.
SONG_STANZAS = SONG_LINES[:2] + [""] + SONG_LINES[2:]


def build(*, header=True, sections=True, blurb=None, body=None, tail=True):
    parts = []
    if header:
        parts += ["3 Contributors", "Some Song Title Lyrics"]
    if blurb:
        parts.append(blurb)
    lines = body or SONG_LINES
    if sections:
        parts.append("[Strophe 1]")
        parts += lines[:2]
        parts.append("[Refrain]")
        parts += lines[2:]
    else:
        parts += lines
    if tail:
        parts += ["You might also like", "12Embed"]
    return "\n".join(parts)


def test_strips_header_sections_and_tail():
    assert clean_lines(build()) == SONG_STANZAS


def test_drops_contributor_and_embed_markers():
    out = clean_lines(build())
    assert not any("Contributor" in l for l in out)
    assert not any(l.endswith("Embed") for l in out)
    assert not any("might also like" in l for l in out)


def test_section_markers_become_stanza_breaks():
    out = clean_lines(build())
    assert not any(l.startswith("[") and l.endswith("]") for l in out)
    assert [l for l in out if l] == SONG_LINES
    assert out.count("") == 1


def test_blank_runs_collapse_and_edges_are_trimmed():
    raw = "\n".join(["[Verse]", "", "", "one", "two", "", "", "[Chorus]", "", "three", ""])
    assert clean_lines(raw) == ["one", "two", "", "three"]


def test_regression_keeps_line_containing_the_word_lyrics():
    """The old read-time filter dropped any line containing 'lyrics'."""
    body = SONG_LINES + ["I never read the lyrics twice"]
    out = clean_lines(build(body=body))
    assert "I never read the lyrics twice" in out


def test_blurb_removed_when_song_has_no_sections():
    blurb = ("This song was recorded in a single afternoon and became the "
             "best known track from the album that followed it.")
    body = SONG_LINES + ["Two more lines to clear", "the six line threshold"]
    out = clean_lines(build(sections=False, blurb=blurb, body=body))
    assert blurb not in out
    assert out == body


def test_blurb_kept_when_song_is_sectioned():
    """A [Section] marker is a hard boundary, so no heuristic is needed."""
    blurb = ("This song was recorded in a single afternoon and became the "
             "best known track from the album that followed it.")
    out = clean_lines(build(sections=True, blurb=blurb))
    assert out == SONG_STANZAS


def test_short_song_is_never_blurb_trimmed():
    """Guard against over-trimming: too few lines to judge shape reliably."""
    body = ["A long opening sentence that runs well past eighty characters "
            "and ends with a full stop.", "short line", "another short line"]
    out = clean_lines(build(sections=False, body=body, header=False, tail=False))
    assert len(out) == 3


def test_empty_input_yields_no_lines():
    assert clean_lines("") == []
    assert clean_lines("3 Contributors\nTitle Lyrics") == []
