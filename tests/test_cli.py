"""CLI argument handling and command wiring."""

import pytest

from hyprmuse import cli, library
from hyprmuse.sources.base import Item, SourceError
from tests.conftest import make_subject


def run(argv, capsys):
    code = cli.main(argv)
    return code, capsys.readouterr()


def test_bare_invocation_defaults_to_quote(capsys):
    """hyprlock calls the binary with no arguments."""
    library.save(make_subject())
    code, out = run([], capsys)
    assert code == 0 and "—" in out.out


def test_leading_flag_still_reaches_quote(capsys):
    library.save(make_subject())
    code, out = run(["--width", "30"], capsys)
    assert code == 0 and out.out.strip()


def test_quote_with_no_library_is_not_an_error(capsys):
    code, out = run(["quote"], capsys)
    assert code == 0
    assert "add" in out.out


def test_list_reports_subjects_and_totals(capsys):
    library.save(make_subject(name="Alpha", n_items=4))
    code, out = run(["list"], capsys)
    assert code == 0
    assert "Alpha" in out.out
    assert "1 subjects, 4 items total" in out.out


def test_list_when_empty(capsys):
    code, out = run(["list"], capsys)
    assert code == 0 and "No subjects yet" in out.out


def test_sources_lists_all_adapters(capsys):
    code, out = run(["sources"], capsys)
    assert code == 0
    for name in ("genius", "wikiquote", "poetrydb", "gutenberg"):
        assert name in out.out


def test_remove_deletes_a_subject(capsys):
    library.save(make_subject(source="genius", source_id="7", name="Gone"))
    code, out = run(["remove", "genius:7"], capsys)
    assert code == 0 and "Removed Gone" in out.out
    assert library.load_all() == []


def test_remove_unknown_subject_errors(capsys):
    code, out = run(["remove", "nope"], capsys)
    assert code == 1 and "no subject matching" in out.err


def test_remove_ambiguous_token_errors(capsys):
    library.save(make_subject(source="genius", source_id="1", name="Same Name"))
    library.save(make_subject(source="poetrydb", source_id="2", name="Same Name"))
    code, out = run(["remove", "Same Name"], capsys)
    assert code == 1 and "ambiguous" in out.err


def test_update_with_nothing_stored_errors(capsys):
    code, out = run(["update", "--all"], capsys)
    assert code == 1 and "nothing to update" in out.err


def test_quote_domain_filter(capsys):
    library.save(make_subject(source="genius", source_id="1", domain="music",
                              name="Musician"))
    library.save(make_subject(source="poetrydb", source_id="2", domain="poetry",
                              name="Poet"))
    code, out = run(["quote", "--domain", "poetry"], capsys)
    assert code == 0 and "Poet" in out.out


def test_quote_seed_is_reproducible(capsys):
    library.save(make_subject(n_items=10))
    _, a = run(["quote", "--seed", "4"], capsys)
    _, b = run(["quote", "--seed", "4"], capsys)
    assert a.out == b.out


def test_quote_width_is_respected(capsys):
    library.save(make_subject(items=None, n_items=1, n_lines=1))
    long_subject = make_subject(source="poetrydb", source_id="9", name="Long")
    long_subject.items[0].lines = ["word " * 60]
    library.save(long_subject)
    code, out = run(["quote", "--source", "poetrydb", "--width", "20",
                     "--max-lines", "0"], capsys)
    body = out.out.split("\n\n")[0]
    assert all(len(l) <= 20 for l in body.splitlines())


def test_quote_max_chars_picks_something_that_fits(capsys):
    subj = make_subject(items=[
        Item(lines=["word " * 40], atomic=True),
        Item(lines=["tiny"], atomic=True),
    ])
    library.save(subj)
    for _ in range(10):
        code, out = run(["quote", "--max-chars", "10"], capsys)
        assert code == 0
        assert out.out.split("\n\n")[0] == "tiny"


def test_unknown_source_is_rejected_by_the_parser(capsys):
    with pytest.raises(SystemExit):
        cli.main(["add", "X", "--source", "notasource"])


def test_help_exits_cleanly():
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0


EBOOK = """The Project Gutenberg eBook of Die Verwandlung

Title: Die Verwandlung

Author: Franz Kafka

Language: German

*** START OF THE PROJECT GUTENBERG EBOOK DIE VERWANDLUNG ***

Als Gregor Samsa eines Morgens aus unruhigen Träumen erwachte, fand er sich
in seinem Bett zu einem ungeheueren Ungeziefer verwandelt.

*** END OF THE PROJECT GUTENBERG EBOOK DIE VERWANDLUNG ***
"""


def test_update_keeps_a_gutenberg_book_title_as_the_work(capsys, monkeypatch,
                                                         fake_client, fake_response):
    """Regression: update rebuilt the search hit from the stored subject and
    gutenberg.fetch read the author from it as the work, so every quote was
    attributed "— Franz Kafka: Franz Kafka"."""
    from hyprmuse import sources
    from hyprmuse.sources import gutenberg
    client = fake_client({f"{gutenberg.BASE}/cache/epub/22367/pg22367.txt":
                          fake_response(text=EBOOK)})
    monkeypatch.setitem(sources.REGISTRY, "gutenberg", gutenberg.Gutenberg(client))
    library.save(make_subject(source="gutenberg", source_id="22367",
                              name="Franz Kafka", domain="prose", items=[
                                  Item(lines=["old"], work="Die Verwandlung",
                                       atomic=True)]))
    code, _ = run(["update", "gutenberg:22367"], capsys)
    (subject,) = library.load_all()
    assert code == 0
    assert subject.name == "Franz Kafka"
    assert {i.work for i in subject.items} == {"Die Verwandlung"}


def test_quote_max_chars_holds_even_when_nothing_fits(capsys):
    """Regression: the fallback for an over-long library capped lines only,
    so a lone 200-character quote was printed in full under --max-chars 30."""
    library.save(make_subject(items=[Item(lines=["word " * 40], atomic=True)]))
    code, out = run(["quote", "--max-chars", "30"], capsys)
    body = out.out.split("\n\n")[0].splitlines()
    assert code == 0
    assert sum(len(ln) for ln in body) <= 30
    assert body[-1].endswith("…")


def test_update_all_goes_on_after_a_source_answers_garbage(capsys, monkeypatch,
                                                           fake_client, fake_response):
    from hyprmuse import sources
    from hyprmuse.sources import gutenberg, wikiquote
    garbage = fake_client({
        fake_client.url("https://en.wikiquote.org/w/api.php", {
            "action": "parse", "page": "Somebody", "prop": "wikitext", "format": "json"}):
        fake_response(text="<html>maintenance</html>")})
    books = fake_client({f"{gutenberg.BASE}/cache/epub/22367/pg22367.txt":
                         fake_response(text=EBOOK)})
    monkeypatch.setitem(sources.REGISTRY, "wikiquote", wikiquote.Wikiquote(garbage))
    monkeypatch.setitem(sources.REGISTRY, "gutenberg", gutenberg.Gutenberg(books))
    library.save(make_subject(source="wikiquote", source_id="en:Somebody",
                              name="Somebody", domain="quotations"))
    library.save(make_subject(source="gutenberg", source_id="22367", name="Franz Kafka",
                              domain="prose", items=[Item(lines=["old"], atomic=True)]))
    code, out = run(["update", "--all"], capsys)
    assert code == 0
    assert "failed" in out.err
    kafka = next(s for s in library.load_all() if s.source == "gutenberg")
    assert kafka.items[0].lines != ["old"]


def test_update_keeps_the_stored_subject_when_genius_is_rate_limited(capsys, monkeypatch,
                                                                    fake_client, fake_response):
    """Regression (#12): a re-harvest that lost songs to a 429 replaced the full one."""
    from hyprmuse import sources
    from hyprmuse.sources import genius
    songs = [{"title": t, "url": f"https://genius.com/{t}",
              "primary_artist": {"id": 7, "name": "Element of Crime", "url": ""}}
             for t in ("first", "second")]
    client = fake_client({
        fake_client.url(f"{genius.API}/artists/7/songs", {"page": 1, "sort": "popularity"}):
        fake_response({"response": {"next_page": None, "songs": songs}}),
        "https://genius.com/first": fake_response(
            text='<div data-lyrics-container="true">Still here</div>'),
        "https://genius.com/second": SourceError("https://genius.com/second returned HTTP 429"),
    })
    monkeypatch.setitem(sources.REGISTRY, "genius", genius.Genius(client))
    stored = make_subject(source="genius", source_id="7", name="Element of Crime",
                          items=[Item(lines=["first"], atomic=False),
                                 Item(lines=["second"], atomic=False)])
    path = library.save(stored)
    before = path.read_bytes()
    code, out = run(["update", "genius:7"], capsys)
    assert code == 1
    assert "HTTP 429" in out.err
    assert path.read_bytes() == before
