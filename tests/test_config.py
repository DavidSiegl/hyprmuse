"""Config loading and its fallbacks."""

from hyprmuse import config


def test_defaults_when_no_file():
    cfg = config.load_config()
    assert cfg["lines"] == config.DEFAULTS["lines"]
    assert cfg["weighting"] == "subject"
    assert cfg["subjects"] == {}


def _write(text):
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.CONFIG_FILE.write_text(text, encoding="utf-8")


def test_user_values_override_defaults():
    _write("[quote]\nlines = 9\nwidth = 33\n")
    cfg = config.load_config()
    assert cfg["lines"] == 9
    assert cfg["width"] == 33
    assert cfg["max_lines"] == config.DEFAULTS["max_lines"]  # untouched


def test_per_subject_settings_are_read():
    _write('[subjects."genius:342499"]\nweight = 2.5\nenabled = false\n')
    subjects = config.load_config()["subjects"]
    assert subjects["genius:342499"]["weight"] == 2.5
    assert subjects["genius:342499"]["enabled"] is False


def test_broken_toml_falls_back_to_defaults():
    _write("[quote\nlines = ")
    cfg = config.load_config()
    assert cfg["lines"] == config.DEFAULTS["lines"]


def test_unknown_keys_are_ignored():
    _write("[quote]\nnonsense = 1\nlines = 4\n")
    cfg = config.load_config()
    assert cfg["lines"] == 4
    assert "nonsense" not in cfg


def test_fit_keys_are_read():
    _write("[quote]\nmax_chars = 120\nmin_line_chars = 4\n")
    cfg = config.load_config()
    assert cfg["max_chars"] == 120
    assert cfg["min_line_chars"] == 4


def test_paths_are_namespaced_under_the_app():
    assert config.APP == "hyprmuse"
