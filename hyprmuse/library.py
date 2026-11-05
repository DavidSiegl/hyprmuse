"""On-disk store: one JSON file per subject under the XDG data directory."""

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
    return config.SUBJECTS_DIR / f"{source}--{slugify(source_id)}.json"


def save(subject: Subject) -> Path:
    """Write a subject atomically so a crash can never truncate the store."""
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
    """Every stored subject.

    A file that cannot be read, is not JSON, or does not have a subject's shape
    is skipped, not fatal: one bad file must not cost the lockscreen its quote.
    """
    if not config.SUBJECTS_DIR.is_dir():
        return []
    out = []
    for path in sorted(config.SUBJECTS_DIR.glob("*.json")):
        try:
            out.append(_to_subject(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
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
    path = subject_path(subject.source, subject.source_id)
    if path.exists():
        path.unlink()
        return True
    return False
