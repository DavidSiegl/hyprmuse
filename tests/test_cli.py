"""CLI argument handling and command wiring."""

import pytest

from hyprmuse import cli, library
from hyprmuse.sources.base import Item
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
