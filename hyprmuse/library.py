"""On-disk store: one JSON file per subject under the XDG data directory."""

import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .sources.base import Item, Subject

SCHEMA = 1


def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text)
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = re.sub(r"[^a-zA-Z0-9]+", "-", norm).strip("-").lower()
    return norm or "unnamed"


def subject_path(source: str, source_id: str) -> Path:
    """The file the subject ``source``/``source_id`` is saved to.

    The name is ``<source>--<slug>-<hash>.json``: the slug keeps it readable,
    and the hash, of the exact id, keeps ids that slugify alike (any two
    titles in a non-Latin script, say) in separate files.
    """
    digest = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:10]
    return config.SUBJECTS_DIR / f"{source}--{slugify(source_id)}-{digest}.json"


def _unhashed_file(source: str, source_id: str) -> Path | None:
    """The subject's file under its name without a hash, if it holds this subject.

    Releases up to 0.3.2 saved a subject as ``<source>--<slug>.json``, a name
    ids that slugify alike shared, so such a file is the subject's only if it
    holds this very (source, source_id). None when there is no such file, or
    it cannot be read.
    """
    path = config.SUBJECTS_DIR / f"{source}--{slugify(source_id)}.json"
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        if (stored["source"], stored["source_id"]) == (source, source_id):
            return path
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def save(subject: Subject) -> Path:
    """Write a subject to ``subject_path``, atomically so a crash cannot truncate it.

    Replaces the subject's earlier file, including one under its name
    without a hash (see ``_unhashed_file``). Returns the path written. Raises
    OSError when the file cannot be written or the unhashed one moved.
    """
    config.SUBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    path = subject_path(subject.source, subject.source_id)
    payload = {
        "schema": SCHEMA,
        "source": subject.source,
        "source_id": subject.source_id,
        "name": subject.name,
        "domain": subject.domain,
        "lang": subject.lang,
        "url": subject.url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "attribution": subject.attribution,
        "items": [
            {"work": i.work, "url": i.url, "atomic": i.atomic,
             "note": i.note, "lines": i.lines}
            for i in subject.items
        ],
    }
    fd, tmp = tempfile.mkstemp(dir=config.SUBJECTS_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        # Moving the unhashed file onto the new name first means a concurrent
        # load_all sees the subject once at every moment, never twice or not at all.
        unhashed = _unhashed_file(subject.source, subject.source_id)
        if unhashed is not None:
            os.replace(unhashed, path)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


class _NotASubject(ValueError):
    """A subject file's JSON is not shaped as ``save`` writes it."""


def _to_subject(stored) -> Subject:
    """The Subject a parsed subject file holds.

    Raises _NotASubject, naming the field, when ``stored`` is not shaped as
    ``save`` writes it: every text field a str, ``atomic`` a bool, ``lines`` a
    list of str. ``domain``, ``lang``, ``url``, ``attribution``, ``items`` and
    each item's fields but ``lines`` may be missing, and get their defaults.
    """
    if not isinstance(stored, dict):
        raise _NotASubject("not a JSON object")
    items = _field(stored, "items", list, [])
    for item in items:
        if not isinstance(item, dict):
            raise _NotASubject("an item is not a JSON object")
        lines = _field(item, "lines", list)
        if not all(isinstance(ln, str) for ln in lines):
            raise _NotASubject("an item's lines are not all text")
    return Subject(
        source=_field(stored, "source", str),
        source_id=_field(stored, "source_id", str),
        name=_field(stored, "name", str),
        domain=_field(stored, "domain", str, "unknown"),
        lang=_field(stored, "lang", str, "en"),
        url=_field(stored, "url", str, ""),
        attribution=_field(stored, "attribution", dict, {}),
        items=[
            Item(lines=i["lines"], work=_field(i, "work", str, ""),
                 url=_field(i, "url", str, ""), atomic=_field(i, "atomic", bool, False),
                 note=_field(i, "note", str, ""))
            for i in items
        ],
    )


_REQUIRED = object()


def _field(stored: dict, key: str, kind: type, default=_REQUIRED):
    """``stored[key]``, or ``default`` when it is missing and one is given.

    Raises _NotASubject naming ``key`` when it is missing with no default, or
    is not a ``kind``.
    """
    if key not in stored:
        if default is _REQUIRED:
            raise _NotASubject(f"{key} is missing")
        return default
    if not isinstance(stored[key], kind):
        raise _NotASubject(f"{key} is not {kind.__name__}")
    return stored[key]


def load_all() -> list[Subject]:
    """Every stored subject.

    A file that cannot be read, is not JSON, or is not shaped as ``save``
    writes it is skipped with a line on stderr naming it, not fatal: one bad
    file must not cost the lockscreen its quote.
    """
    if not config.SUBJECTS_DIR.is_dir():
        return []
    out = []
    for path in sorted(config.SUBJECTS_DIR.glob("*.json")):
        try:
            out.append(_to_subject(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError) as exc:
            print(f"hyprmuse: skipping {path}: {exc}", file=sys.stderr)
    return out


def find(token: str) -> list[Subject]:
    """The stored subjects a token on the command line means.

    The subject whose ``key`` the token is, if one is stored; otherwise every
    subject whose name contains the token, ignoring case. An empty token
    means no subject.
    """
    if not token:
        return []
    subjects = load_all()
    exact = [s for s in subjects if s.key == token]
    if exact:
        return exact
    low = token.lower()
    return [s for s in subjects if low in s.name.lower()]


def remove(subject: Subject) -> bool:
    """Delete the subject's stored files; returns whether there was one.

    A file under its name without a hash (see ``_unhashed_file``) counts too.
    Raises OSError when a file that is there cannot be deleted.
    """
    removed = False
    for path in (subject_path(subject.source, subject.source_id),
                 _unhashed_file(subject.source, subject.source_id)):
        if path is None:
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        removed = True
    return removed
