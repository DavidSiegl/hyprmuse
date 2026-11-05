"""XDG paths and user configuration."""

import math
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

# The least value each whole-number setting in DEFAULTS takes. A fraction is
# cut to a whole number, as int() cuts it.
LEAST = {"lines": 1, "width": 0, "max_lines": 0, "max_chars": 0,
         "avoid_repeats": 0, "min_line_chars": 0}

# The values "weighting" takes.
WEIGHTINGS = ("subject", "quote")


def load_config() -> dict:
    """Merge config.toml over DEFAULTS, falling back on whatever is broken.

    Returns DEFAULTS' keys plus "subjects", which maps a subject key to the
    settings given for it: "enabled" (a bool; false leaves the subject out of
    quotes) and "weight" (a float >= 0 scaling how often it is drawn), each
    present only when set. Every value holds to LEAST and WEIGHTINGS, so
    callers need not check it.

    A missing or unparsable file gives the defaults and no subject settings.
    A value of the wrong type or out of range is dropped, so the default
    stands, and a line on stderr names it: the lockscreen must still get a
    quote, and the user must be able to find out why their setting does
    nothing.
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
    for key in DEFAULTS:
        if key not in quote:
            continue
        given = quote[key]
        if key == "weighting":
            if given in WEIGHTINGS:
                cfg[key] = given
            else:
                _ignore(f"[quote] {key}", given, f"one of {', '.join(map(repr, WEIGHTINGS))}")
        elif (n := _number(given, LEAST[key])) is not None:
            cfg[key] = int(n)
        else:
            _ignore(f"[quote] {key}", given, f"a number >= {LEAST[key]}")
    for key, table in _table(raw.get("subjects", {}), "[subjects]").items():
        where = f'[subjects."{key}"]'
        given_settings = _table(table, where)
        settings = subjects[key] = {}
        if "enabled" in given_settings:
            if isinstance(given_settings["enabled"], bool):
                settings["enabled"] = given_settings["enabled"]
            else:
                _ignore(f"{where} enabled", given_settings["enabled"], "true or false")
        if "weight" in given_settings:
            if (n := _number(given_settings["weight"], 0)) is not None:
                settings["weight"] = n
            else:
                _ignore(f"{where} weight", given_settings["weight"], "a number >= 0")
    return cfg


def _table(given, where: str) -> dict:
    """``given`` if it is a TOML table, else {} with a warning naming ``where``."""
    if isinstance(given, dict):
        return given
    _warn(f"{where} is not a table; ignoring it")
    return {}


def _number(given, least: float) -> float | None:
    """``given`` as a float if it is a finite number >= ``least``, else None.

    A bool is not a number here, though Python makes it an int.
    """
    if isinstance(given, bool) or not isinstance(given, (int, float)):
        return None
    if not math.isfinite(given) or given < least:
        return None
    return float(given)


def _ignore(where: str, given, expected: str) -> None:
    _warn(f"{where} = {given!r} is not {expected}; using the default")


def _warn(msg: str) -> None:
    print(f"hyprmuse: config.toml: {msg}", file=sys.stderr)
