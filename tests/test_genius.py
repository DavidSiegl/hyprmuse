"""The Genius boilerplate cleaner - the part with a real bug history."""

import pytest

from hyprmuse.sources import genius
from hyprmuse.sources.base import SourceError
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


PAGE = """<html><body>
<div data-lyrics-container="true">
  <div data-exclude-from-selection="true">
    <button>3 Contributors</button><h2>Delmenhorst Lyrics</h2>
  </div>
  [Strophe 1:]<br/>
  Ich bin jetzt immer da, wo du nicht bist<br/>
  Und das ist immer <a href="/x"><span>Delmenhorst</span></a>
  <span style="opacity:0" tabindex="0"></span><br/>
  Und wo zu sein, wo du nie warst<br/><br/>
  [Refrain:]<br/>
  Hinter <a href="/y"><span>Huchting</span></a> ist ein Graben<br/>
  Der ist weder breit noch tief<br/>
</div>
</body></html>"""


def test_lyrics_text_keeps_annotated_lines_whole():
    """Genius wraps annotated phrases in inline <a>; a line must survive that.

    The old separator-joined get_text() broke "Und das ist immer Delmenhorst"
    into three lines and doubled every <br>, so every line became its own
    stanza and the selector could only ever quote one line.
    """
    lines = clean_lines(genius.lyrics_text(PAGE))
    assert lines == [
        "Ich bin jetzt immer da, wo du nicht bist",
        "Und das ist immer Delmenhorst",
        "Und wo zu sein, wo du nie warst",
        "",
        "Hinter Huchting ist ein Graben",
        "Der ist weder breit noch tief",
    ]


def test_lyrics_text_without_a_container_is_none():
    assert genius.lyrics_text("<html><body>no lyrics here</body></html>") is None


def songs_url(fake_client, page, artist_id="7"):
    return fake_client.url(f"{genius.API}/artists/{artist_id}/songs",
                           {"page": page, "sort": "popularity"})


def song(title, artist_id=7, artist="Element of Crime"):
    return {"title": title, "url": f"https://genius.com/{title.lower()}",
            "primary_artist": {"id": artist_id, "name": artist,
                               "url": "https://genius.com/artists/eoc"}}


def test_fetch_names_the_subject_from_the_artists_own_songs(fake_client,
                                                            fake_response):
    """fetch gets only the id, so the name must come from Genius itself."""
    client = fake_client({
        songs_url(fake_client, 1): fake_response({"response": {"next_page": None, "songs": [
            song("guest", artist_id=99, artist="Someone Else"),
            song("Delmenhorst"),
        ]}}),
        "https://genius.com/delmenhorst": fake_response(text=PAGE),
    })
    subject = genius.Genius(client).fetch("7")
    assert subject.name == "Element of Crime"
    assert subject.url == "https://genius.com/artists/eoc"
    assert [i.work for i in subject.items] == ["Delmenhorst"]
    assert "https://genius.com/guest" not in client.requested


def test_fetch_follows_the_song_list_across_pages(fake_client, fake_response):
    client = fake_client({
        songs_url(fake_client, 1): fake_response(
            {"response": {"next_page": 2, "songs": [song("first")]}}),
        songs_url(fake_client, 2): fake_response(
            {"response": {"next_page": None, "songs": [song("second")]}}),
        "https://genius.com/first": fake_response(text=PAGE),
        "https://genius.com/second": fake_response(text=PAGE),
    })
    subject = genius.Genius(client).fetch("7")
    assert [i.work for i in subject.items] == ["first", "second"]
    assert client.requested[:2] == [songs_url(fake_client, 1), songs_url(fake_client, 2)]


def test_search_offers_only_artist_hits_with_an_id(fake_client, fake_response):
    url = fake_client.url(f"{genius.API}/search/artist", {"q": "element"})
    client = fake_client({url: fake_response({"response": {"sections": [
        {"type": "song", "hits": [{"result": {"id": 1, "name": "A Song"}}]},
        {"type": "artist", "hits": [{"result": {"id": 7, "name": "Element of Crime"}},
                                    {"result": {"name": "No Id"}}]},
    ]}})})
    hits = genius.Genius(client).search("element")
    assert [(h.source_id, h.name) for h in hits] == [("7", "Element of Crime")]


def test_fetch_skips_a_song_genius_has_no_page_for(fake_client, fake_response):
    client = fake_client({
        songs_url(fake_client, 1): fake_response(
            {"response": {"next_page": None, "songs": [song("gone"), song("kept")]}}),
        "https://genius.com/kept": fake_response(text=PAGE),
    })
    subject = genius.Genius(client).fetch("7")
    assert [i.work for i in subject.items] == ["kept"]


def test_fetch_fails_when_a_song_request_fails(fake_client, fake_response):
    """A partial harvest would replace the stored subject with fewer songs (#12)."""
    client = fake_client({
        songs_url(fake_client, 1): fake_response(
            {"response": {"next_page": None, "songs": [song("first"), song("second")]}}),
        # Client.get raises a SourceError that is not NotFound for a 429, a
        # 5xx or a dropped connection alike (tests/test_client.py).
        "https://genius.com/first": SourceError("https://genius.com/first returned HTTP 429"),
        "https://genius.com/second": fake_response(text=PAGE),
    })
    with pytest.raises(SourceError, match="genius.com/first"):
        genius.Genius(client).fetch("7")


def endless_catalogue(fake_client, fake_response, per_page, pages):
    """Routes for an artist whose every song-list page names a next one.

    Page n holds songs "s<n>-1" .. "s<n>-<per_page>", each with lyrics.
    """
    routes = {}
    for n in range(1, pages + 1):
        titles = [f"s{n}-{i}" for i in range(1, per_page + 1)]
        routes[songs_url(fake_client, n)] = fake_response(
            {"response": {"next_page": n + 1, "songs": [song(t) for t in titles]}})
        for t in titles:
            routes[f"https://genius.com/{t}"] = fake_response(text=PAGE)
    return fake_client(routes)


@pytest.mark.parametrize(("per_page", "kept"), [
    (3, ["s1-1", "s1-2", "s1-3", "s2-1"]),  # the limit falls inside page 2
    (2, ["s1-1", "s1-2", "s2-1", "s2-2"]),  # page 2 ends on the limit
])
def test_fetch_stops_listing_songs_at_the_limit(fake_client, fake_response, monkeypatch,
                                                per_page, kept):
    """Regression: a wrong match with ~23,000 songs paged the list until Genius
    answered 403 and blocked the machine."""
    monkeypatch.setattr(genius, "MAX_SONGS", 4)
    client = endless_catalogue(fake_client, fake_response, per_page=per_page, pages=10)
    said = []
    subject = genius.Genius(client).fetch("7", said.append)
    listed = [u for u in client.requested if "/songs?" in u]
    assert listed == [songs_url(fake_client, 1), songs_url(fake_client, 2)]
    assert [i.work for i in subject.items] == kept
    assert "kept the 4 most popular of more songs" in said


def test_fetch_takes_every_song_of_an_artist_up_to_the_limit(fake_client, fake_response,
                                                             monkeypatch):
    monkeypatch.setattr(genius, "MAX_SONGS", 4)
    client = fake_client({
        songs_url(fake_client, 1): fake_response(
            {"response": {"next_page": 2, "songs": [song("first"), song("second")]}}),
        songs_url(fake_client, 2): fake_response(
            {"response": {"next_page": None, "songs": [song("third"), song("fourth")]}}),
        **{f"https://genius.com/{t}": fake_response(text=PAGE)
           for t in ("first", "second", "third", "fourth")},
    })
    said = []
    subject = genius.Genius(client).fetch("7", said.append)
    assert [i.work for i in subject.items] == ["first", "second", "third", "fourth"]
    assert not any(m.startswith("kept") for m in said)
