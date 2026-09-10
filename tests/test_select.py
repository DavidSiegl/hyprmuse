"""Quote selection: slicing, weighting, filtering, repeat avoidance."""

import json

from hyprmuse import config, library, select
from hyprmuse.sources.base import Item
from tests.conftest import make_subject


def cfg(**over):
    base = config.load_config()
    base.update(over)
    return base


def test_sliceable_item_yields_a_contiguous_window():
    item = Item(lines=[f"l{i}" for i in range(10)], atomic=False)
    import random
    lines = select._extract(item, 3, random.Random(0))
    assert len(lines) == 3
    start = item.lines.index(lines[0])
    assert item.lines[start:start + 3] == lines


def test_atomic_item_is_returned_whole():
    item = Item(lines=[f"l{i}" for i in range(10)], atomic=True)
    import random
    assert select._extract(item, 3, random.Random(0)) == item.lines


def test_short_item_returns_all_its_lines():
    item = Item(lines=["only", "two"], atomic=False)
    import random
    assert select._extract(item, 5, random.Random(0)) == ["only", "two"]


VERSE = ["v1", "v2", "v3", "v4"]
CHORUS = ["c1", "c2", "c3"]
SONG = Item(lines=VERSE + [""] + CHORUS, atomic=False)


def test_window_never_straddles_a_stanza_break():
    import random
    for seed in range(50):
        out = select._extract(SONG, 3, random.Random(seed))
        assert "" not in out
        assert all(l in VERSE for l in out) or all(l in CHORUS for l in out)


def test_both_stanzas_are_reachable():
    import random
    firsts = {select._extract(SONG, 2, random.Random(s))[0] for s in range(50)}
    assert firsts & set(VERSE) and firsts & set(CHORUS)


def test_one_line_stanzas_are_avoided_when_real_ones_exist():
    import random
    item = Item(lines=["[tag]", "", "a", "b", "", "c", "d"], atomic=False)
    for seed in range(30):
        assert "[tag]" not in select._extract(item, 2, random.Random(seed))


def test_one_line_stanza_is_used_when_nothing_else_exists():
    import random
    item = Item(lines=["lonely", "", "alone"], atomic=False)
    assert select._extract(item, 3, random.Random(0)) in (["lonely"], ["alone"])


def test_short_lines_are_dropped_by_min_chars():
    import random
    item = Item(lines=["Oh", "a real line", "-", "another real line"], atomic=False)
    out = select._extract(item, 4, random.Random(0), min_chars=3)
    assert out == ["a real line", "another real line"]


def test_min_chars_applies_to_atomic_items_too():
    import random
    item = Item(lines=["A whole quotation.", "I"], atomic=True)
    assert select._extract(item, 1, random.Random(0), min_chars=2) == ["A whole quotation."]


def test_stored_libraries_without_breaks_slice_as_before():
    """Files harvested before stanza marks exist behave as one long stanza."""
    import random
    item = Item(lines=[f"l{i}" for i in range(10)], atomic=False)
    out = select._extract(item, 3, random.Random(0))
    start = item.lines.index(out[0])
    assert item.lines[start:start + 3] == out


def test_fit_rejects_by_lines_and_chars_after_wrapping():
    fit = select.Fit(width=10, max_lines=2, max_chars=0)
    assert fit.accepts(["short", "lines"])
    assert not fit.accepts(["this line is far too long to fit"])  # wraps to 4
    assert not select.Fit(max_chars=5).accepts(["123456"])
    assert select.UNCONSTRAINED.accepts(["x" * 1000] * 100)


def test_window_shrinks_from_the_end_until_it_fits():
    import random
    item = Item(lines=["a", "b", "c", "d", "e", "f"], atomic=False)
    fit = select.Fit(max_lines=2)
    for seed in range(20):
        out = select._extract(item, 4, random.Random(seed), fit=fit)
        assert len(out) == 2
        assert item.lines[item.lines.index(out[0]):][:2] == out


def test_atomic_item_that_cannot_fit_is_rejected():
    import random
    item = Item(lines=["x" * 100], atomic=True)
    assert select._extract(item, 3, random.Random(0), fit=select.Fit(max_chars=50)) == []


def test_pick_returns_none_on_empty_library():
    assert select.pick(cfg(), num_lines=3) is None


def test_pick_returns_a_quote():
    library.save(make_subject())
    chosen = select.pick(cfg(), num_lines=3)
    assert chosen is not None
    assert chosen.lines
    assert chosen.subject.name == "Test Subject"


def test_seed_makes_selection_deterministic():
    library.save(make_subject(n_items=8))
    a = select.pick(cfg(), num_lines=3, seed=11)
    b = select.pick(cfg(), num_lines=3, seed=11)
    assert a.lines == b.lines and a.item.work == b.item.work


def test_domain_and_source_filters():
    library.save(make_subject(source="genius", source_id="1", domain="music"))
    library.save(make_subject(source="poetrydb", source_id="2", domain="poetry",
                              name="A Poet"))
    assert select.pick(cfg(), num_lines=2, domain="poetry").subject.domain == "poetry"
    assert select.pick(cfg(), num_lines=2, source="genius").subject.source == "genius"


def test_subject_filter_matches_on_name():
    library.save(make_subject(source_id="1", name="Alpha Band"))
    library.save(make_subject(source="poetrydb", source_id="2", name="Beta Poet"))
    assert select.pick(cfg(), num_lines=2, subject="beta").subject.name == "Beta Poet"


def test_disabled_subject_is_excluded():
    library.save(make_subject(source="genius", source_id="1"))
    conf = cfg()
    conf["subjects"] = {"genius:1": {"enabled": False}}
    assert select.candidates(conf) == []


def test_subject_weighting_balances_unequal_libraries():
    """A huge subject must not swamp a small one under the default weighting."""
    library.save(make_subject(source="genius", source_id="1", name="Big",
                              n_items=200))
    library.save(make_subject(source="poetrydb", source_id="2", name="Small",
                              n_items=2))
    picks = [select.pick(cfg(avoid_repeats=0), num_lines=2).subject.name
             for _ in range(300)]
    assert 0.3 < picks.count("Small") / len(picks) < 0.7


def test_quote_weighting_favours_the_larger_subject():
    library.save(make_subject(source="genius", source_id="1", name="Big",
                              n_items=200))
    library.save(make_subject(source="poetrydb", source_id="2", name="Small",
                              n_items=2))
    picks = [select.pick(cfg(weighting="quote", avoid_repeats=0),
                         num_lines=2).subject.name for _ in range(300)]
    assert picks.count("Big") > picks.count("Small") * 5


def test_explicit_weight_zero_excludes_a_subject():
    library.save(make_subject(source="genius", source_id="1", name="Muted"))
    library.save(make_subject(source="poetrydb", source_id="2", name="Heard"))
    conf = cfg(avoid_repeats=0)
    conf["subjects"] = {"genius:1": {"weight": 0}}
    names = {select.pick(conf, num_lines=2).subject.name for _ in range(60)}
    assert names == {"Heard"}


def test_recent_history_is_written_and_capped():
    library.save(make_subject(n_items=30))
    for _ in range(15):
        select.pick(cfg(avoid_repeats=5), num_lines=2)
    recent = json.loads(config.RECENT_FILE.read_text(encoding="utf-8"))
    assert len(recent) == 5


def test_seeded_pick_does_not_pollute_history():
    library.save(make_subject())
    select.pick(cfg(), num_lines=2, seed=3)
    assert not config.RECENT_FILE.exists()


def test_repeats_avoided_within_the_window():
    library.save(make_subject(n_items=40, n_lines=3, atomic=True))
    seen = [select.pick(cfg(avoid_repeats=20), num_lines=3).fingerprint()
            for _ in range(20)]
    assert len(set(seen)) == len(seen)


def test_fingerprint_is_stable_and_content_dependent():
    library.save(make_subject())
    a = select.pick(cfg(), num_lines=3, seed=5)
    b = select.pick(cfg(), num_lines=3, seed=5)
    assert a.fingerprint() == b.fingerprint()


def test_unreadable_recent_file_is_tolerated():
    library.save(make_subject())
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.RECENT_FILE.write_text("garbage", encoding="utf-8")
    assert select.pick(cfg(), num_lines=2) is not None


def test_subjects_with_no_items_are_skipped():
    library.save(make_subject(items=[]))
    assert select.pick(cfg(), num_lines=2) is None


def test_pick_prefers_an_item_that_fits():
    library.save(make_subject(items=[
        Item(lines=["a " * 60], atomic=True),
        Item(lines=["fits"], atomic=True),
    ]))
    fit = select.Fit(width=20, max_lines=2)
    for _ in range(20):
        assert select.pick(cfg(avoid_repeats=0), num_lines=1, fit=fit).lines == ["fits"]


def test_pick_falls_back_when_nothing_fits():
    """A trimmed quote beats a blank lockscreen."""
    library.save(make_subject(items=[Item(lines=["a " * 60], atomic=True)]))
    chosen = select.pick(cfg(), num_lines=1, fit=select.Fit(width=20, max_lines=1))
    assert chosen is not None and chosen.lines == [("a " * 60).strip()]


def test_pick_honours_min_line_chars_from_config():
    library.save(make_subject(items=[Item(lines=["Oh", "a proper line"])]))
    chosen = select.pick(cfg(min_line_chars=3), num_lines=2)
    assert chosen.lines == ["a proper line"]
    chosen = select.pick(cfg(min_line_chars=0, avoid_repeats=0), num_lines=2)
    assert chosen.lines == ["Oh", "a proper line"]
