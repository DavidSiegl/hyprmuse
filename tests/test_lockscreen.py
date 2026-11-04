"""The lockscreen quote: slicing, fitting, weighting, filtering, repeats, layout.

Everything goes through ``lockscreen.quote``, the module's only interface.
"""

import json

from hyprmuse import config, library, lockscreen
from hyprmuse.sources.base import Item
from tests.conftest import make_subject

# A box that never wraps or trims, so the body is exactly the lines drawn.
OPEN_BOX = dict(width=0, max_lines=0, max_chars=0)


def cfg(**over):
    base = config.load_config()
    base.update(over)
    return base


def draw(conf=None, **kw):
    """(body lines, attribution line, note lines) of one quote, or None."""
    text = lockscreen.quote(conf if conf is not None else cfg(), **kw)
    if text is None:
        return None
    body, _, tail = text.partition("\n\n")
    attribution, *note = tail.split("\n")
    return body.split("\n"), attribution, note


def body(conf=None, **kw):
    return draw(conf, **kw)[0]


def store(*items, **subject):
    library.save(make_subject(items=list(items), **subject))


def bodies(item, seeds=50, **over):
    """Bodies drawn from a library holding only ``item``, one per seed.

    Draws in the open box and keeps one-letter lines unless ``over`` says
    otherwise, so the body is exactly the slice taken.
    """
    store(item)
    conf = cfg(**{"avoid_repeats": 0, "min_line_chars": 0, **OPEN_BOX, **over})
    return [body(conf, seed=s) for s in range(seeds)]


# --- slicing -----------------------------------------------------------------

def test_sliceable_item_yields_a_contiguous_window():
    item = Item(lines=[f"l{i}" for i in range(10)])
    for out in bodies(item, lines=3):
        start = item.lines.index(out[0])
        assert item.lines[start:start + 3] == out


def test_atomic_item_is_returned_whole():
    item = Item(lines=[f"l{i}" for i in range(10)], atomic=True)
    assert set(map(tuple, bodies(item, lines=3))) == {tuple(item.lines)}


def test_short_item_returns_all_its_lines():
    assert bodies(Item(lines=["only", "two"]), seeds=5, lines=5) == [["only", "two"]] * 5


VERSE = ["v1", "v2", "v3", "v4"]
CHORUS = ["c1", "c2", "c3"]
SONG = Item(lines=VERSE + [""] + CHORUS)


def test_window_never_straddles_a_stanza_break():
    for out in bodies(SONG, lines=3):
        assert all(ln in VERSE for ln in out) or all(ln in CHORUS for ln in out)


def test_both_stanzas_are_reachable():
    firsts = {out[0] for out in bodies(SONG, lines=2)}
    assert firsts & set(VERSE) and firsts & set(CHORUS)


def test_one_line_stanzas_are_avoided_when_real_ones_exist():
    item = Item(lines=["[tag]", "", "a", "b", "", "c", "d"])
    assert all("[tag]" not in out for out in bodies(item, seeds=30, lines=2))


def test_one_line_stanza_is_used_when_nothing_else_exists():
    item = Item(lines=["lonely", "", "alone"])
    assert all(out in (["lonely"], ["alone"]) for out in bodies(item, seeds=10, lines=3))


def test_short_lines_are_dropped_by_min_line_chars():
    item = Item(lines=["Oh", "a real line", "-", "another real line"])
    assert bodies(item, seeds=1, lines=4, min_line_chars=3) == [
        ["a real line", "another real line"]]


def test_min_line_chars_applies_to_atomic_items_too():
    item = Item(lines=["A whole quotation.", "I"], atomic=True)
    assert bodies(item, seeds=1, min_line_chars=2) == [["A whole quotation."]]


def test_min_line_chars_from_config_can_be_disabled():
    item = Item(lines=["Oh", "a proper line"])
    assert bodies(item, seeds=1, lines=2, min_line_chars=0) == [["Oh", "a proper line"]]


def test_item_with_no_usable_line_yields_nothing():
    store(Item(lines=["I", "-"]))
    assert lockscreen.quote(cfg(min_line_chars=3)) is None


# --- fitting the box ---------------------------------------------------------

def test_window_shrinks_from_the_end_until_it_fits():
    item = Item(lines=["a", "b", "c", "d", "e", "f"])
    for out in bodies(item, seeds=20, lines=4, **{**OPEN_BOX, "max_lines": 2}):
        assert len(out) == 2
        assert item.lines[item.lines.index(out[0]):][:2] == out


def test_an_item_that_fits_is_preferred():
    store(Item(lines=["a " * 60], atomic=True), Item(lines=["fits"], atomic=True))
    conf = cfg(avoid_repeats=0, width=20, max_lines=2, max_chars=0)
    assert {tuple(body(conf, seed=s)) for s in range(20)} == {("fits",)}


def test_long_lines_wrap_to_width():
    store(Item(lines=["A considerably longer sentence that will certainly need to "
                      "be folded across several lines to fit."], atomic=True))
    out = body(cfg(width=25, max_lines=0, max_chars=0))
    assert len(out) > 1 and all(len(ln) <= 25 for ln in out)


def test_when_nothing_fits_the_best_effort_is_cut_to_max_lines():
    """A trimmed quote beats a blank lockscreen."""
    store(Item(lines=[f"line {i}" for i in range(20)], atomic=True))
    assert body(cfg(width=40, max_lines=3, max_chars=0)) == ["line 0", "line 1", "line 2"]


def test_when_nothing_fits_whole_lines_go_before_any_line_is_cut():
    store(Item(lines=["first line here", "second line here"], atomic=True))
    assert body(cfg(width=0, max_lines=0, max_chars=20)) == ["first line here"]


def test_when_one_line_alone_is_too_long_it_is_cut_at_a_word():
    store(Item(lines=["word " * 40], atomic=True))
    (line,) = body(cfg(width=0, max_lines=0, max_chars=30))
    assert len(line) <= 30 and line.endswith("…")
    assert line[:-1].split() == ["word"] * len(line[:-1].split())


def test_a_single_overlong_word_is_hard_cut():
    store(Item(lines=["x" * 100], atomic=True))
    assert body(cfg(width=0, max_lines=0, max_chars=10)) == ["x" * 9 + "…"]


# --- layout ------------------------------------------------------------------

def test_attribution_names_the_work_when_there_is_one():
    store(Item(lines=["a line"], work="A Song"), name="Some Name")
    assert draw()[1] == "— Some Name: A Song"


def test_attribution_without_a_work_is_just_the_name():
    store(Item(lines=["a line"], work=""), name="Some Name")
    assert lockscreen.quote(cfg()) == "a line\n\n— Some Name"


def test_note_is_included_only_when_requested():
    store(Item(lines=["quote"], note="A Book, 1920", atomic=True))
    assert draw()[2] == []
    assert draw(show_note=True)[2] == ["A Book, 1920"]


# --- the library and its filters ---------------------------------------------

def test_empty_library_yields_nothing():
    assert lockscreen.quote(cfg()) is None


def test_subjects_with_no_items_are_skipped():
    library.save(make_subject(items=[]))
    assert lockscreen.quote(cfg()) is None


def test_seed_makes_the_quote_deterministic():
    library.save(make_subject(n_items=8))
    assert lockscreen.quote(cfg(), seed=11) == lockscreen.quote(cfg(), seed=11)


def test_domain_and_source_filters():
    library.save(make_subject(source="genius", source_id="1", domain="music",
                              name="Musician"))
    library.save(make_subject(source="poetrydb", source_id="2", domain="poetry",
                              name="A Poet"))
    assert draw(domain="poetry")[1].startswith("— A Poet")
    assert draw(source="genius")[1].startswith("— Musician")


def test_subject_filter_matches_on_name_or_key():
    library.save(make_subject(source_id="1", name="Alpha Band"))
    library.save(make_subject(source="poetrydb", source_id="2", name="Beta Poet"))
    assert draw(subject="beta")[1].startswith("— Beta Poet")
    assert draw(subject="genius:1")[1].startswith("— Alpha Band")


def test_disabled_subject_is_excluded():
    library.save(make_subject(source="genius", source_id="1"))
    conf = cfg()
    conf["subjects"] = {"genius:1": {"enabled": False}}
    assert lockscreen.quote(conf) is None


# --- weighting ---------------------------------------------------------------

def names_drawn(conf, n=300):
    return [draw(conf)[1].split(":")[0].removeprefix("— ") for _ in range(n)]


def big_and_small():
    library.save(make_subject(source="genius", source_id="1", name="Big",
                              n_items=200))
    library.save(make_subject(source="poetrydb", source_id="2", name="Small",
                              n_items=2))


def test_subject_weighting_balances_unequal_libraries():
    """A huge subject must not swamp a small one under the default weighting."""
    big_and_small()
    picks = names_drawn(cfg(avoid_repeats=0))
    assert 0.3 < picks.count("Small") / len(picks) < 0.7


def test_quote_weighting_favours_the_larger_subject():
    big_and_small()
    picks = names_drawn(cfg(weighting="quote", avoid_repeats=0))
    assert picks.count("Big") > picks.count("Small") * 5


def test_explicit_weight_zero_excludes_a_subject():
    library.save(make_subject(source="genius", source_id="1", name="Muted"))
    library.save(make_subject(source="poetrydb", source_id="2", name="Heard"))
    conf = cfg(avoid_repeats=0)
    conf["subjects"] = {"genius:1": {"weight": 0}}
    assert set(names_drawn(conf, 60)) == {"Heard"}


# --- repeat avoidance --------------------------------------------------------

def test_repeats_are_avoided_within_the_window():
    library.save(make_subject(n_items=40, n_lines=3, atomic=True))
    seen = [lockscreen.quote(cfg(avoid_repeats=20)) for _ in range(20)]
    assert len(set(seen)) == len(seen)


def test_recent_history_is_capped_at_avoid_repeats():
    library.save(make_subject(n_items=30))
    for _ in range(15):
        lockscreen.quote(cfg(avoid_repeats=5))
    assert len(json.loads(config.RECENT_FILE.read_text(encoding="utf-8"))) == 5


def test_seeded_quote_does_not_touch_the_history():
    library.save(make_subject())
    lockscreen.quote(cfg(), seed=3)
    assert not config.RECENT_FILE.exists()


def test_unreadable_history_is_tolerated():
    library.save(make_subject())
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.RECENT_FILE.write_text("garbage", encoding="utf-8")
    assert lockscreen.quote(cfg()) is not None
