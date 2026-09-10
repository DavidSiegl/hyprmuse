"""Format a pick for display: wrap, cap, attribute."""

from .select import Pick
from .text import wrap  # noqa: F401  (re-exported: render.wrap is the public name)

DASH = "—"


def attribution(pick: Pick) -> str:
    who = pick.subject.name
    work = pick.item.work.strip()
    return f"{DASH} {who}: {work}" if work else f"{DASH} {who}"


def render(pick: Pick, *, width: int = 60, max_lines: int = 6,
           show_note: bool = False) -> str:
    # The selector already shrinks a pick to fit; this cap is the safety net
    # for the case where nothing in the library fitted at all.
    body = wrap(pick.lines, width)
    if max_lines > 0 and len(body) > max_lines:
        body = body[:max_lines]
    parts = ["\n".join(body), "", attribution(pick)]
    if show_note and pick.item.note:
        parts.extend(wrap([pick.item.note], width))
    return "\n".join(parts)
