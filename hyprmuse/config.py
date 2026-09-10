"""XDG paths and user configuration."""

import os
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


def load_config() -> dict:
    """Merge config.toml over DEFAULTS. Missing or broken file falls back cleanly."""
    cfg = dict(DEFAULTS)
    cfg["subjects"] = {}
    if not CONFIG_FILE.exists():
        return cfg
    try:
        raw = tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return cfg
    for key in DEFAULTS:
        if key in raw.get("quote", {}):
            cfg[key] = raw["quote"][key]
    cfg["subjects"] = raw.get("subjects", {})
    return cfg
