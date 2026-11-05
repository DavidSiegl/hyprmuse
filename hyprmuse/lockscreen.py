"""The quote hyprlock shows: drawn from the library, fitted to a box, attributed.

Everything about the box (wrapping, line and character caps, what happens when
nothing fits) and about repeat avoidance lives here, behind ``quote``.
"""

import hashlib
import json
import random
import textwrap
from dataclasses import dataclass

from . import config, library
from .sources.base import Item, Subject
from .text import stanzas, wrap

DASH = "—"


def quote(cfg: dict, *, subject: str = "", domain: str = "", source: str = "",
          seed: int | None = None, show_note: bool = False) -> str | None:
    """A random quote from the library, rendered as text for the lockscreen.

    ``cfg`` is a config dict shaped like ``config.load_config()``'s: the keys
    of ``config.DEFAULTS`` (each documented there) plus ``"subjects"``, the
    per-subject ``enabled``/``weight`` table. A caller overriding a setting
    replaces its key before the call.

    ``subject`` (a token, resolved by ``library.find``), ``domain`` and
    ``source`` restrict which stored subjects are drawn from; empty means any.
    ``seed`` makes the draw deterministic and leaves the repeat history alone.
    ``show_note`` appends the item's citation note, when it has one.

    The result is the quote body, a blank line, then "— Name" or "— Name: Work",
    then the note if shown. The body fits the box ``cfg`` describes; when no
    stored quote fits, the best effort is trimmed to it, and only then can a
    line end in "…". Returns None when no stored subject passes the filters,
    or none of their items has a line longer than ``cfg["min_line_chars"]``.

    Unless ``seed`` is set, records the quote in ``config.RECENT_FILE`` so the
    next ``cfg["avoid_repeats"]`` draws avoid it; a failure to write that file
    is ignored, since a read-only home must not break the lockscreen.
    """
    pool = _candidates(cfg, subject=subject, domain=domain, source=source)
    if not pool:
        return None
    rng = random.Random(seed)
    recent = _load_recent()
    keep = int(cfg.get("avoid_repeats", 20))
    weights = [_weight(s, cfg) for s in pool]
    if sum(weights) <= 0:
        weights = [1.0] * len(pool)
    fit = _Fit(width=int(cfg["width"]), max_lines=int(cfg["max_lines"]),
               max_chars=int(cfg["max_chars"]))

    draw = dict(num_lines=int(cfg["lines"]),
                min_chars=int(cfg.get("min_line_chars", 0)),
                recent=recent if keep > 0 else [])
    chosen = _draw(pool, weights, rng, fit=fit, **draw)
    if chosen is None and fit != _UNCONSTRAINED:
        # Nothing in the library fits the box; a trimmed quote beats a blank
        # lockscreen, so draw without it and let _render trim the result.
        chosen = _draw(pool, weights, rng, fit=_UNCONSTRAINED, **draw)
    if chosen is None:
        return None

    if keep > 0 and seed is None:
        _save_recent(recent + [chosen.fingerprint()], keep)
    return _render(chosen, fit, show_note=show_note)


@dataclass(frozen=True)
class _Fit:
    """The box a rendered quote has to fit in. Zero means unconstrained."""

    width: int = 0
    max_lines: int = 0
    max_chars: int = 0  # summed over the wrapped lines, newlines not counted

    def accepts(self, lines: list[str]) -> bool:
        body = wrap(lines, self.width)
        if self.max_lines > 0 and len(body) > self.max_lines:
            return False
        if self.max_chars > 0 and sum(len(ln) for ln in body) > self.max_chars:
            return False
        return True

    def trim(self, lines: list[str]) -> list[str]:
        """Wrap ``lines`` and cut them to the box, keeping at least one line.

        Whole lines go from the end first; only a single line still over
        max_chars is cut inside, at a word boundary, and marked with "…".
        """
        body = wrap(lines, self.width)
        if self.max_lines > 0:
            body = body[:self.max_lines]
        if self.max_chars <= 0:
            return body
        while len(body) > 1 and sum(len(ln) for ln in body) > self.max_chars:
            body = body[:-1]
        if body and len(body[0]) > self.max_chars:
            short = textwrap.shorten(body[0], width=self.max_chars, placeholder="…")
            # shorten() yields the bare placeholder when the first word alone
            # is too long; a hard cut keeps some text instead.
            if short == "…":
                short = body[0][:self.max_chars - 1] + "…"
            body = [short]
        return body


_UNCONSTRAINED = _Fit()


@dataclass
class _Pick:
    """One drawn quote: the lines taken from ``item``, before wrapping."""

    subject: Subject
    item: Item
    lines: list[str]

    def fingerprint(self) -> str:
        """Identifies the quote in the repeat history; equal text, equal print."""
        seed = f"{self.subject.source}:{self.subject.source_id}:" + "|".join(self.lines)
        return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def _render(pick: _Pick, fit: _Fit, *, show_note: bool) -> str:
    who = pick.subject.name
    work = pick.item.work.strip()
    parts = ["\n".join(fit.trim(pick.lines)), "",
             f"{DASH} {who}: {work}" if work else f"{DASH} {who}"]
    if show_note and pick.item.note:
        parts.extend(wrap([pick.item.note], fit.width))
    return "\n".join(parts)


def _load_recent() -> list[str]:
    try:
        return json.loads(config.RECENT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_recent(seen: list[str], keep: int) -> None:
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        config.RECENT_FILE.write_text(json.dumps(seen[-keep:]), encoding="utf-8")
    except OSError:
        pass  # a read-only home must not break the lockscreen


def _candidates(cfg: dict, *, subject: str, domain: str,
                source: str) -> list[Subject]:
    """Stored subjects with items, minus those disabled in config or filtered out."""
    out = []
    for subj in library.find(subject) if subject else library.load_all():
        if _settings(subj, cfg).get("enabled") is False:
            continue
        if domain and subj.domain != domain:
            continue
        if source and subj.source != source:
            continue
        if subj.items:
            out.append(subj)
    return out


def _settings(subj: Subject, cfg: dict) -> dict:
    """The settings config.toml gives ``subj`` in ``[subjects."<key>"]``; {} if none."""
    return cfg.get("subjects", {}).get(subj.key, {})


def _weight(subj: Subject, cfg: dict) -> float:
    base = float(_settings(subj, cfg).get("weight", 1.0))
    # "quote" weighting makes every stored quote equally likely, so prolific
    # subjects dominate; "subject" (the default) gives each subject equal say.
    return base * len(subj.items) if cfg.get("weighting") == "quote" else base


def _extract(item: Item, num_lines: int, rng: random.Random, *,
             min_chars: int, fit: _Fit) -> list[str]:
    """Lines to quote from one item, or [] if nothing from it fits.

    Sliceable items are cut within a single stanza (blank-line delimited), so
    a window never straddles a verse and its chorus. If the window overflows
    the fit it is shortened from the end, a line at a time, before giving up.
    """
    groups = stanzas(item.lines, min_chars)
    if not groups:
        return []
    if item.atomic:
        whole = [ln for g in groups for ln in g]
        return whole if fit.accepts(whole) else []
    # A one-line stanza is usually a stray refrain tag or an orphaned line;
    # prefer real stanzas whenever the item has any.
    usable = [g for g in groups if len(g) >= 2] or groups
    stanza = rng.choice(usable)
    take = min(num_lines, len(stanza))
    start = rng.randint(0, len(stanza) - take)
    for n in range(take, 0, -1):
        window = stanza[start:start + n]
        if fit.accepts(window):
            return window
    return []


def _draw(pool: list[Subject], weights: list[float], rng: random.Random, *,
          num_lines: int, min_chars: int, fit: _Fit, recent: list[str],
          tries: int = 40) -> _Pick | None:
    """Weighted random pick, retrying briefly to avoid a recently shown one."""
    chosen = None
    for _ in range(tries):
        subj = rng.choices(pool, weights=weights, k=1)[0]
        item = rng.choice(subj.items)
        lines = _extract(item, num_lines, rng, min_chars=min_chars, fit=fit)
        if not lines:
            continue
        chosen = _Pick(subj, item, lines)
        if chosen.fingerprint() not in recent:
            break
    return chosen
