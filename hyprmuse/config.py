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

# The least value each whole-number setting in DEFAULTS takes. A fraction is
# cut to a whole number, as int() cuts it.
LEAST = {"lines": 1, "width": 0, "max_lines": 0, "max_chars": 0,
         "avoid_repeats": 0, "min_line_chars": 0}

# The most any number setting takes, per-subject weight included. It keeps
# every sum the weighted draw makes finite.
MOST = 1_000_000

# The values "weighting" takes.
WEIGHTINGS = ("subject", "quote")

# The environment variable that holds the Genius API access token; it wins
# over config.toml's [genius] access_token.
GENIUS_TOKEN_ENV = "GENIUS_ACCESS_TOKEN"  # noqa: S105 - a variable's name, not a token


def load_config() -> dict:
    """Merge config.toml over DEFAULTS, falling back on whatever is broken.

    Returns DEFAULTS' keys plus "subjects", which maps a subject key to the
    settings given for it: "enabled" (a bool; false leaves the subject out of
    quotes) and "weight" (a float from 0 to MOST scaling how often it is drawn), each
    present only when set. Every value holds to LEAST, MOST and WEIGHTINGS, so
    callers need not check it.

    A missing or unparsable file gives the defaults and no subject settings.
    A value of the wrong type or out of range is dropped, so the default
    stands, and a line on stderr names it: the lockscreen must still get a
    quote, and the user must be able to find out why their setting does
    nothing.
    """
    subjects: dict[str, dict] = {}
    cfg = {**DEFAULTS, "subjects": subjects}
    raw = _read_file()
    cfg.update(_quote_settings(_table(raw.get("quote", {}), "[quote]")))
    for key, table in _table(raw.get("subjects", {}), "[subjects]").items():
        subjects[key] = _subject_settings(table, f'[subjects."{key}"]')
    return cfg


def genius_token() -> str | None:
    """The Genius API access token the user set; None when there is none.

    GENIUS_TOKEN_ENV wins when it is set and not blank; otherwise the string
    ``access_token`` in config.toml's [genius] table. Surrounding whitespace
    is dropped. A token that is not a string, or that holds inner whitespace,
    control characters or non-ASCII ones, is ignored with a line on stderr
    that does not repeat it: an HTTP header cannot carry it, and the error
    requests raises for one would print the secret. An unreadable file counts
    as setting nothing, as in ``load_config``.
    """
    if token := os.environ.get(GENIUS_TOKEN_ENV, "").strip():
        if _sendable(token):
            return token
        print(f"hyprmuse: {GENIUS_TOKEN_ENV} {_UNSENDABLE}; ignoring it", file=sys.stderr)
    given = _table(_read_file().get("genius", {}), "[genius]").get("access_token")
    if given is None:
        return None
    if not isinstance(given, str):
        _warn("[genius] access_token is not a string; ignoring it")
        return None
    token = given.strip()
    if token and not _sendable(token):
        _warn(f"[genius] access_token {_UNSENDABLE}; ignoring it")
        return None
    return token or None


_UNSENDABLE = "holds whitespace, control or non-ASCII characters"


def _sendable(token: str) -> bool:
    """Whether ``token`` can go into an HTTP header as it is."""
    return token.isascii() and token.isprintable() and " " not in token


def _read_file() -> dict:
    """config.toml's top-level tables; {} when it is missing or unparsable."""
    try:
        return tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # missing or unreadable; not UTF-8, or not TOML
        return {}


def _quote_settings(given: dict) -> dict:
    """The settings of DEFAULTS that the [quote] table ``given`` sets validly.

    Warns about each one it leaves out.
    """
    settings = {}
    for key in (k for k in DEFAULTS if k in given):
        if key == "weighting":
            if given[key] in WEIGHTINGS:
                settings[key] = given[key]
            else:
                _ignore(f"[quote] {key}", given[key],
                        f"one of {', '.join(map(repr, WEIGHTINGS))}")
        elif (n := _number(given[key], LEAST[key])) is not None:
            settings[key] = int(n)
        else:
            _ignore(f"[quote] {key}", given[key], f"a number from {LEAST[key]} to {MOST}")
    return settings


def _subject_settings(table, where: str) -> dict:
    """The "enabled" and "weight" that ``table``, found at ``where``, sets validly.

    Warns about each one it leaves out, and about ``table`` not being a table.
    """
    given = _table(table, where)
    settings: dict = {}
    if "enabled" in given:
        if isinstance(given["enabled"], bool):
            settings["enabled"] = given["enabled"]
        else:
            _ignore(f"{where} enabled", given["enabled"], "true or false")
    if "weight" in given:
        if (n := _number(given["weight"], 0)) is not None:
            settings["weight"] = n
        else:
            _ignore(f"{where} weight", given["weight"], f"a number from 0 to {MOST}")
    return settings


def _table(given, where: str) -> dict:
    """``given`` if it is a TOML table, else {} with a warning naming ``where``."""
    if isinstance(given, dict):
        return given
    _warn(f"{where} is not a table; ignoring it")
    return {}


def _number(given, least: float) -> float | None:
    """``given`` as a float if it is a number from ``least`` to MOST, else None.

    A bool is not a number here, though Python makes it an int.
    """
    if isinstance(given, bool) or not isinstance(given, (int, float)):
        return None
    if not least <= given <= MOST:  # also false for nan
        return None
    return float(given)


def _ignore(where: str, given, expected: str) -> None:
    _warn(f"{where} = {given!r} is not {expected}; using the default")


def _warn(msg: str) -> None:
    print(f"hyprmuse: config.toml: {msg}", file=sys.stderr)
