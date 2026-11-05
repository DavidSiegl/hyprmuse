"""On-disk store: one JSON file per subject under the XDG data directory."""

import hashlib
import json
import os
import re
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


def subject_key(source: str, source_id: str) -> str:
    return f"{source}:{source_id}"


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


def _to_subject(data: dict) -> Subject:
    return Subject(
        source=data["source"],
        source_id=data["source_id"],
        name=data["name"],
        domain=data.get("domain", "unknown"),
        lang=data.get("lang", "en"),
        url=data.get("url", ""),
        attribution=data.get("attribution", {}),
        items=[
            Item(lines=i["lines"], work=i.get("work", ""), url=i.get("url", ""),
                 atomic=i.get("atomic", False), note=i.get("note", ""))
            for i in data.get("items", [])
        ],
    )


def load_all() -> list[Subject]:
    """Every stored subject. Unreadable files are skipped, not fatal."""
    if not config.SUBJECTS_DIR.is_dir():
        return []
    out = []
    for path in sorted(config.SUBJECTS_DIR.glob("*.json")):
        try:
            out.append(_to_subject(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError, KeyError):
            continue
    return out


def find(token: str) -> list[Subject]:
    """Resolve 'source:id', or a case-insensitive substring of the name."""
    subjects = load_all()
    if ":" in token:
        src, _, sid = token.partition(":")
        exact = [s for s in subjects
                 if s.source == src and s.source_id == sid]
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
