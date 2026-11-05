"""CLI argument handling and command wiring."""

import pytest

from hyprmuse import cli, config, library
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
    from tests.test_genius import song, songs_url
    client = fake_client({
        songs_url(fake_client, 1): fake_response(
            {"response": {"next_page": None, "songs": [song("first"), song("second")]}}),
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


# A token that is one subject's key and part of another's name.
TOKEN = "genius:2"


def store_key_and_name_lookalikes():
    library.save(make_subject(source_id="2", name="Keyed"))
    library.save(make_subject(source_id="3", name=f"Tribute to {TOKEN}"))


@pytest.mark.parametrize("seed", range(10))
def test_quote_subject_takes_the_subject_whose_key_the_token_is(capsys, seed):
    store_key_and_name_lookalikes()
    code, out = run(["quote", "--subject", TOKEN, "--seed", str(seed)], capsys)
    assert code == 0 and "— Keyed" in out.out


def test_remove_takes_the_subject_whose_key_the_token_is(capsys):
    store_key_and_name_lookalikes()
    code, out = run(["remove", TOKEN], capsys)
    assert code == 0 and "Removed Keyed" in out.out
    assert [s.name for s in library.load_all()] == [f"Tribute to {TOKEN}"]


@pytest.fixture
def fetched(monkeypatch):
    """The ids update asks Genius to fetch; Genius answers each with a fresh subject."""
    from hyprmuse import sources
    ids = []

    class Recorder:
        def fetch(self, source_id, progress=None):
            ids.append(source_id)
            return make_subject(source_id=source_id, name="Fresh")

    monkeypatch.setitem(sources.REGISTRY, "genius", Recorder())
    return ids


def test_update_takes_the_subject_whose_key_the_token_is(capsys, fetched):
    store_key_and_name_lookalikes()
    code, _ = run(["update", TOKEN], capsys)
    assert code == 0 and fetched == ["2"]


def test_update_without_a_token_or_all_names_what_to_do(capsys, fetched):
    library.save(make_subject())
    with pytest.raises(SystemExit):
        run(["update"], capsys)
    assert "one of the arguments token --all is required" in capsys.readouterr().err
    assert fetched == []


def test_update_refuses_a_token_together_with_all(capsys, fetched):
    library.save(make_subject())
    with pytest.raises(SystemExit):
        run(["update", "genius:1", "--all"], capsys)
    assert "not allowed with argument token" in capsys.readouterr().err
    assert fetched == []


def test_update_all_reharvests_every_stored_subject(capsys, fetched):
    library.save(make_subject(source_id="1", name="One"))
    library.save(make_subject(source_id="2", name="Two"))
    code, _ = run(["update", "--all"], capsys)
    assert code == 0 and sorted(fetched) == ["1", "2"]


def test_quote_whose_subjects_are_all_disabled_does_not_ask_to_add_one(capsys):
    library.save(make_subject(source_id="2"))
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.CONFIG_FILE.write_text('[subjects."genius:2"]\nenabled = false\n',
                                  encoding="utf-8")
    code, out = run(["quote", "--subject", "genius:2"], capsys)
    assert code == 0 and "hyprmuse add" not in out.out
    assert "No stored quote passes" in out.out


def test_remove_with_an_empty_token_removes_nothing(capsys):
    library.save(make_subject())
    code, _ = run(["remove", ""], capsys)
    assert code == 1 and len(library.load_all()) == 1


def test_search_prints_the_token_that_names_each_hit(capsys, monkeypatch):
    from hyprmuse import sources
    from hyprmuse.sources.base import Candidate

    class OneHit:
        def search(self, query, lang):
            return [Candidate("genius", "7", "Hit", "music")]

    monkeypatch.setitem(sources.REGISTRY, "genius", OneHit())
    code, out = run(["search", "hit", "--source", "genius"], capsys)
    assert code == 0 and "    genius:7" in out.out.splitlines()


def _write_config(text):
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.CONFIG_FILE.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(("toml", "named"), [
    ('[quote]\nwidth = "wide"\n', "width"),
    ('[subjects."genius:1"]\nweight = "high"\n', "weight"),
])
def test_quote_survives_a_config_value_of_the_wrong_type(capsys, toml, named):
    """Regression (#10): hyprlock shows a blank label when quote dies."""
    library.save(make_subject())
    _write_config(toml)
    code, out = run(["quote"], capsys)
    assert code == 0 and "—" in out.out
    assert named in out.err


def test_quote_survives_a_recent_file_that_is_not_a_list(capsys):
    library.save(make_subject())
    config.RECENT_FILE.write_text("{}", encoding="utf-8")
    code, out = run(["quote"], capsys)
    assert code == 0 and "—" in out.out


def test_quote_and_list_skip_a_subject_file_of_the_wrong_shape(capsys):
    library.save(make_subject())
    (config.SUBJECTS_DIR / "broken.json").write_text(
        '{"source": "genius", "source_id": "2", "name": "Broken", "items": ["oops"]}',
        encoding="utf-8")
    code, out = run(["quote"], capsys)
    assert code == 0 and "—" in out.out
    code, out = run(["list"], capsys)
    assert code == 0 and "Broken" not in out.out


@pytest.fixture
def by_key(monkeypatch):
    """Genius and Wikiquote stand-ins that record what add asks of them.

    Returns a list of ("search", query) and ("fetch", source, source_id) calls.
    """
    from hyprmuse import sources
    from hyprmuse.sources.base import Candidate
    calls = []

    class Recorder:
        def __init__(self, name):
            self.name = name

        def search(self, query, lang):
            calls.append(("search", query))
            return [Candidate(self.name, "found", "Found", "music")]

        def fetch(self, source_id, progress=None):
            calls.append(("fetch", self.name, source_id))
            return make_subject(source=self.name, source_id=source_id, name="Fetched")

    for name in ("genius", "wikiquote"):
        monkeypatch.setitem(sources.REGISTRY, name, Recorder(name))
    return calls


def test_add_fetches_the_subject_a_key_names_without_searching(capsys, by_key):
    """Regression: add searched Genius for "genius:259534" and harvested an
    unrelated artist."""
    code, out = run(["add", "genius:123", "-y"], capsys)
    assert code == 0 and by_key == [("fetch", "genius", "123")]
    assert "Harvesting genius:123 from genius" in out.err


def test_add_splits_a_key_on_its_first_colon_only(capsys, by_key):
    code, _ = run(["add", "wikiquote:en:Arno Schmidt", "-y"], capsys)
    assert code == 0 and by_key == [("fetch", "wikiquote", "en:Arno Schmidt")]


@pytest.mark.parametrize("query", ["Franz Kafka", "Mr. T: The Book", "genius:"])
def test_add_searches_a_query_that_is_not_a_key(capsys, by_key, query):
    code, _ = run(["add", query, "-y", "--source", "genius"], capsys)
    assert code == 0
    assert by_key == [("search", query), ("fetch", "genius", "found")]


def test_add_refuses_a_key_from_another_source_than_source_names(capsys, by_key):
    code, out = run(["add", "genius:123", "--source", "wikiquote"], capsys)
    assert code == 1 and by_key == []
    assert "genius:123" in out.err and "wikiquote" in out.err


def test_add_fails_on_a_key_its_source_cannot_fetch(capsys, monkeypatch, by_key):
    from hyprmuse import sources

    class Gone:
        name = "genius"

        def search(self, query, lang):
            by_key.append(("search", query))
            return []

        def fetch(self, source_id, progress=None):
            raise SourceError("genius: no artist 999")

    monkeypatch.setitem(sources.REGISTRY, "genius", Gone())
    code, out = run(["add", "genius:999", "-y"], capsys)
    assert code == 1 and "no artist 999" in out.err
    assert by_key == [] and library.load_all() == []
