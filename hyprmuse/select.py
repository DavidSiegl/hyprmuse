"""Pick a random quote across the library, avoiding recent repeats."""

import hashlib
import json
import random
from dataclasses import dataclass

from . import config, library
from .sources.base import Item, Subject
from .text import stanzas, wrap


@dataclass(frozen=True)
class Fit:
    """The box a rendered quote has to fit in. Zero means unconstrained."""

    width: int = 0
    max_lines: int = 0
    max_chars: int = 0

    def accepts(self, lines: list[str]) -> bool:
        body = wrap(lines, self.width)
        if self.max_lines > 0 and len(body) > self.max_lines:
            return False
        if self.max_chars > 0 and sum(len(ln) for ln in body) > self.max_chars:
            return False
        return True


UNCONSTRAINED = Fit()


@dataclass
class Pick:
    subject: Subject
    item: Item
    lines: list[str]

    def fingerprint(self) -> str:
        seed = f"{self.subject.source}:{self.subject.source_id}:" + "|".join(self.lines)
        return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


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


def candidates(cfg: dict, *, subject: str = "", domain: str = "",
               source: str = "") -> list[Subject]:
    """Stored subjects, minus those disabled in config or excluded by filters."""
    subjects = library.load_all()
    out = []
    for subj in subjects:
        settings = cfg.get("subjects", {}).get(
            library.subject_key(subj.source, subj.source_id), {})
        if settings.get("enabled") is False:
            continue
        if domain and subj.domain != domain:
            continue
        if source and subj.source != source:
            continue
        if subject and subject.lower() not in subj.name.lower() \
                and subject != library.subject_key(subj.source, subj.source_id):
            continue
        if subj.items:
            out.append(subj)
    return out


def _weight(subj: Subject, cfg: dict) -> float:
    settings = cfg.get("subjects", {}).get(
        library.subject_key(subj.source, subj.source_id), {})
    base = float(settings.get("weight", 1.0))
    # "quote" weighting makes every stored quote equally likely, so prolific
    # subjects dominate; "subject" (the default) gives each subject equal say.
    return base * len(subj.items) if cfg.get("weighting") == "quote" else base


def _extract(item: Item, num_lines: int, rng: random.Random, *,
             min_chars: int = 0, fit: Fit = UNCONSTRAINED) -> list[str]:
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
          num_lines: int, min_chars: int, fit: Fit, recent: list[str],
          tries: int = 40) -> Pick | None:
    """Weighted random pick, retrying briefly to avoid a recently shown one."""
    chosen = None
    for _ in range(tries):
        subj = rng.choices(pool, weights=weights, k=1)[0]
        item = rng.choice(subj.items)
        lines = _extract(item, num_lines, rng, min_chars=min_chars, fit=fit)
        if not lines:
            continue
        chosen = Pick(subj, item, lines)
        if chosen.fingerprint() not in recent:
            break
    return chosen


def pick(cfg: dict, *, num_lines: int, subject: str = "", domain: str = "",
         source: str = "", seed: int | None = None,
         fit: Fit = UNCONSTRAINED) -> Pick | None:
    """Choose one quote that fits, preferring one not shown recently."""
    pool = candidates(cfg, subject=subject, domain=domain, source=source)
    if not pool:
        return None
    rng = random.Random(seed)
    recent = _load_recent()
    keep = int(cfg.get("avoid_repeats", 20))
    min_chars = int(cfg.get("min_line_chars", 0))
    weights = [_weight(s, cfg) for s in pool]
    if sum(weights) <= 0:
        weights = [1.0] * len(pool)

    draw = dict(num_lines=num_lines, min_chars=min_chars,
                recent=recent if keep > 0 else [])
    chosen = _draw(pool, weights, rng, fit=fit, **draw)
    if chosen is None and fit != UNCONSTRAINED:
        # Nothing in the library fits the box; a trimmed quote beats a blank
        # lockscreen, so fall back and let render cap it.
        chosen = _draw(pool, weights, rng, fit=UNCONSTRAINED, **draw)

    if chosen and keep > 0 and seed is None:
        _save_recent(recent + [chosen.fingerprint()], keep)
    return chosen
