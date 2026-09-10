"""Line-level text helpers shared by harvesting, selection and rendering.

A blank string inside ``Item.lines`` marks a stanza break. Sources emit it at
harvest time and the selector slices within the stanzas it delimits.
"""

import textwrap


def mark_stanzas(lines: list[str]) -> list[str]:
    """Strip every line, collapse runs of blanks to one, drop leading/trailing blanks."""
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line:
            out.append(line)
        elif out and out[-1]:
            out.append("")
    if out and not out[-1]:
        out.pop()
    return out


def stanzas(lines: list[str], min_chars: int = 0) -> list[list[str]]:
    """Split on blank lines; drop lines shorter than min_chars and empty stanzas."""
    groups: list[list[str]] = [[]]
    for raw in lines:
        line = raw.strip()
        if not line:
            if groups[-1]:
                groups.append([])
        elif len(line) >= min_chars:
            groups[-1].append(line)
    return [g for g in groups if g]


def wrap(lines: list[str], width: int) -> list[str]:
    """Wrap each line to width, preserving line breaks that are already there.

    Verse and lyric line breaks are meaningful, so they are kept; only lines
    that genuinely overflow (prose quotations) get folded.
    """
    out: list[str] = []
    for line in lines:
        if width <= 0 or len(line) <= width:
            out.append(line)
        else:
            out.extend(textwrap.wrap(line, width=width) or [line])
    return out
