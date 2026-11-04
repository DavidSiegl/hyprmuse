"""Format a pick for display: wrap, cap, attribute."""

import textwrap

from .select import Pick
from .text import wrap  # noqa: F401  (re-exported: render.wrap is the public name)

DASH = "—"


def attribution(pick: Pick) -> str:
    who = pick.subject.name
    work = pick.item.work.strip()
    return f"{DASH} {who}: {work}" if work else f"{DASH} {who}"


def _trim(body: list[str], max_lines: int, max_chars: int) -> list[str]:
    """Cut wrapped lines to the caps (0 = none), keeping at least one line.

    Whole lines go from the end first; only a single line still over
    max_chars is cut inside, at a word boundary, and marked with an ellipsis.
    """
    if max_lines > 0:
        body = body[:max_lines]
    if max_chars <= 0:
        return body
    while len(body) > 1 and sum(len(ln) for ln in body) > max_chars:
        body = body[:-1]
    if body and len(body[0]) > max_chars:
        short = textwrap.shorten(body[0], width=max_chars, placeholder="…")
        # shorten() yields the bare placeholder when the first word alone is
        # too long; a hard cut keeps some text instead.
        body = [short if short != "…" else body[0][:max_chars - 1] + "…"]
    return body


def render(pick: Pick, *, width: int = 60, max_lines: int = 6,
           max_chars: int = 0, show_note: bool = False) -> str:
    # The selector already shrinks a pick to fit; this trim is the safety net
    # for the case where nothing in the library fitted at all.
    body = _trim(wrap(pick.lines, width), max_lines, max_chars)
    parts = ["\n".join(body), "", attribution(pick)]
    if show_note and pick.item.note:
        parts.extend(wrap([pick.item.note], width))
    return "\n".join(parts)
