"""XDG paths and user configuration."""

import os
import sys
import tomllib
from pathlib import Path

APP = "hyprmuse"


def _xdg(env: str, fallback: str) -> Path:
    root = os.environ.get(env)
    return (Path(root) if root else Path.home() / fallback) / APP


DATA_DIR = _xdg("XDG_DATA_HOME", ".local/share")
CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config")
SUBJECTS_DIR = DATA_DIR / "subjects"
RECENT_FILE = DATA_DIR / "recent.json"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULTS = {
    "lines": 3,
    "width": 60,
    "max_lines": 6,
    "max_chars": 0,  # total characters after wrapping, 0 = unlimited
    "weighting": "subject",  # "subject" or "quote"
    "avoid_repeats": 20,
    "min_line_chars": 2,  # lines shorter than this ("-", "I") are skipped when slicing
}


# The types each per-subject setting in [subjects."<key>"] takes; other keys
# there are ignored. "enabled" = false leaves a subject out of quotes, and
# "weight" scales how often it is drawn (1.0 when unset).
SUBJECT_SETTINGS = {"enabled": (bool,), "weight": (int, float)}


def load_config() -> dict:
    """Merge config.toml over DEFAULTS, falling back on whatever is broken.

    Returns DEFAULTS' keys plus "subjects", which maps a subject key to its
    settings (SUBJECT_SETTINGS). A missing or unparsable file gives the
    defaults and no subject settings. A value of the wrong type is dropped,
    so the default stands, and a line on stderr names it: the lockscreen must
    still get a quote, and the user must be able to find out why their
    setting does nothing.
    """
    subjects: dict[str, dict] = {}
    cfg = {**DEFAULTS, "subjects": subjects}
    if not CONFIG_FILE.exists():
        return cfg
    try:
        raw = tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return cfg
    quote = _table(raw.get("quote", {}), "[quote]")
    for key, default in DEFAULTS.items():
        if key in quote and _typed(quote[key], (type(default),), f"[quote] {key}"):
            cfg[key] = quote[key]
    for key, table in _table(raw.get("subjects", {}), "[subjects]").items():
        subjects[key] = {
            name: setting for name, setting in _table(table, f'[subjects."{key}"]').items()
            if name not in SUBJECT_SETTINGS
            or _typed(setting, SUBJECT_SETTINGS[name], f'[subjects."{key}"] {name}')}
    return cfg


def _table(value, where: str) -> dict:
    """``value`` if it is a TOML table, else {} with a warning naming ``where``."""
    if isinstance(value, dict):
        return value
    _warn(f"{where} is not a table; ignoring it")
    return {}


def _typed(value, kinds: tuple[type, ...], where: str) -> bool:
    """Whether ``value`` is one of ``kinds``; warns naming ``where`` when not.

    A bool counts only where bool is listed, though Python makes it an int.
    """
    if isinstance(value, kinds) and (bool in kinds or not isinstance(value, bool)):
        return True
    expected = " or ".join(k.__name__ for k in kinds)
    _warn(f"{where} = {value!r} is not {expected}; using the default")
    return False


def _warn(msg: str) -> None:
    print(f"hyprmuse: config.toml: {msg}", file=sys.stderr)
