"""Line-level helpers: wrapping keeps meaningful breaks, folds only overflow."""

from hyprmuse.text import wrap


def test_short_lines_are_left_alone():
    assert wrap(["short", "also short"], 40) == ["short", "also short"]


def test_long_line_is_folded_to_width():
    out = wrap([("word " * 40).strip()], 30)
    assert len(out) > 1
    assert all(len(l) <= 30 for l in out)


def test_existing_line_breaks_are_preserved():
    """Verse and lyric breaks carry meaning and must survive wrapping."""
    lines = ["first line", "second line", "third line"]
    assert wrap(lines, 80) == lines


def test_width_zero_disables_wrapping():
    assert wrap(["x" * 200], 0) == ["x" * 200]
