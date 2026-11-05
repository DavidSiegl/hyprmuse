"""Config loading and its fallbacks."""

import pytest

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


def test_a_value_of_the_wrong_type_keeps_the_default_and_says_so(capsys):
    # TOML's true is a Python int too; it still is not a width.
    _write('[quote]\nwidth = true\nlines = 4\n[subjects."genius:1"]\nweight = 2\nenabled = "no"\n')
    cfg = config.load_config()
    assert cfg["width"] == config.DEFAULTS["width"]
    assert cfg["lines"] == 4
    assert cfg["subjects"]["genius:1"] == {"weight": 2}
    err = capsys.readouterr().err
    assert "[quote] width = True is not a number from 0 to" in err
    assert '[subjects."genius:1"] enabled' in err


@pytest.mark.parametrize(("toml", "named"), [
    ("[quote]\nlines = 0\n", "[quote] lines = 0"),
    ("[quote]\nmax_chars = -5\n", "[quote] max_chars = -5"),
    ("[quote]\nwidth = inf\n", "[quote] width = inf"),
    ('[quote]\nweighting = "quotes"\n', "[quote] weighting = 'quotes'"),
    ('[subjects."genius:1"]\nweight = inf\n', '[subjects."genius:1"] weight = inf'),
    ('[subjects."genius:1"]\nweight = nan\n', '[subjects."genius:1"] weight = nan'),
    ('[subjects."genius:1"]\nweight = -1\n', '[subjects."genius:1"] weight = -1'),
    ('[subjects."genius:1"]\nweight = 1e308\n', '[subjects."genius:1"] weight = 1e+308'),
    ("[quote]\nwidth = " + "9" * 400 + "\n", "[quote] width = 999"),
])
def test_a_value_out_of_range_keeps_the_default_and_says_so(capsys, toml, named):
    _write(toml)
    cfg = config.load_config()
    assert {k: cfg[k] for k in config.DEFAULTS} == config.DEFAULTS
    assert "weight" not in cfg["subjects"].get("genius:1", {})
    assert named in capsys.readouterr().err


def test_a_fraction_is_cut_to_a_whole_number():
    _write("[quote]\nwidth = 40.7\n")
    assert config.load_config()["width"] == 40


def test_a_section_that_is_not_a_table_is_ignored(capsys):
    _write('quote = 5\nsubjects = "x"\n')
    cfg = config.load_config()
    assert cfg["lines"] == config.DEFAULTS["lines"]
    assert cfg["subjects"] == {}
    assert "[quote] is not a table" in capsys.readouterr().err


def test_weighting_is_read():
    _write('[quote]\nweighting = "quote"\n')
    assert config.load_config()["weighting"] == "quote"


def test_a_file_that_is_not_utf8_falls_back_to_defaults():
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.CONFIG_FILE.write_bytes(b"[quote]\nlines = 4 # \xff\n")
    assert config.load_config()["lines"] == config.DEFAULTS["lines"]
