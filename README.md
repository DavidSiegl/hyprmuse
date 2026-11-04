<h1 align="center">
  <img src="https://raw.githubusercontent.com/DavidSiegl/hyprmuse/main/assets/logo.svg" width="84" height="84" alt="">
  <br>
  hyprmuse
</h1>

<p align="center">
  Random quotes from musicians, literary authors, poets and public-domain books,
  for your <code>hyprlock</code> screen.
</p>

Name a subject, hyprmuse harvests them from a fitting source into a local
library, and prints a random quote on demand. Everything is stored offline, so
the lockscreen never waits on the network.

## Sources

| Source | Domain | Covers | Licence |
|---|---|---|---|
| `wikiquote` | quotations | authors, philosophers, scientists, films, TV, proverbs — any language edition | CC BY-SA |
| `genius` | music | song lyrics for any artist | scraped, personal use |
| `poetrydb` | poetry | ~130 classic poets, full poems | public domain |
| `gutenberg` | prose | passages from public-domain books | public domain |

Sources fall into two kinds. **Sliceable** items (lyrics, poems) are quoted as a
random window of consecutive lines taken from within one stanza, so a slice
never runs from a verse into its chorus. **Atomic** items (a Wikiquote
quotation, a prose passage) are quoted whole and word-wrapped.

Every pick is checked against the box it has to fit (`width`, `max_lines`,
`max_chars`). A window that overflows is shortened a line at a time, and an
item that cannot fit at all is skipped in favour of another. Only when nothing
in the library fits does the output get cut off.

Libraries harvested before stanza breaks were stored still work, but slice as
one long stanza. Run `hyprmuse update --all` once to pick the breaks up.

## Setup

Download the Linux binary from the [latest release](https://github.com/DavidSiegl/hyprmuse/releases/latest),
which needs no Python, and check it:

```bash
curl -LO https://github.com/DavidSiegl/hyprmuse/releases/latest/download/hyprmuse-linux-x86_64
curl -LO https://github.com/DavidSiegl/hyprmuse/releases/latest/download/hyprmuse-linux-x86_64.sha256
sha256sum -c hyprmuse-linux-x86_64.sha256
install -D -m 755 hyprmuse-linux-x86_64 ~/.local/bin/hyprmuse
```

Or install it from PyPI, which needs Python 3.14; uv fetches it if the system has none:

```bash
uv tool install hyprmuse     # or: pipx install hyprmuse
```

Or run it from a checkout with `uv sync`, then `uv run hyprmuse` in place of `hyprmuse`
below.

## Usage

```bash
# add subjects — omit --source to search every source and pick from a list
hyprmuse add "Element of Crime" --source genius
hyprmuse add "Ingeborg Bachmann" --source wikiquote --lang de
hyprmuse add "Emily Dickinson" --source poetrydb
hyprmuse add "Frankenstein" --source gutenberg

hyprmuse search "Nietzsche" --lang de   # look without harvesting
hyprmuse list                           # what's stored
hyprmuse update --all                   # re-harvest everything
hyprmuse remove "genius:342499"

hyprmuse quote                          # a random quote
hyprmuse quote --domain poetry --width 50
hyprmuse quote --max-lines 4 --max-chars 160  # fit a small label
hyprmuse quote --source wikiquote --note
hyprmuse quote --seed 42                # deterministic
```

`--lang` selects the Wikiquote language edition (`de`, `en`, `fr`, …). Harvesting
is throttled and cached; `add` is the slow step, `quote` reads only local files.

## Hyprlock integration

```ini
label {
    monitor =
    text = cmd[update:0] ~/.local/bin/hyprmuse quote --width 60
    color = rgba(200, 200, 200, 1.0)
    font_size = 20
    font_family = Noto Sans
    position = 0, 80
    halign = center
    valign = center
}
```

From a checkout, the command is `/path/to/hyprmuse/.venv/bin/hyprmuse`.
`quote.py` is kept as a compatibility shim, so an existing config pointing at
`/path/to/hyprmuse/quote.py` keeps working — only the directory name changed.

## Configuration

Optional, at `~/.config/hyprmuse/config.toml`:

```toml
[quote]
lines = 3           # lines taken from sliceable items
width = 60          # wrap width, 0 disables wrapping
max_lines = 6       # most lines after wrapping, 0 disables
max_chars = 0       # most characters after wrapping, 0 disables
min_line_chars = 2  # skip lines shorter than this ("-", "I") when slicing
weighting = "subject"  # "subject" = every subject equally likely
                       # "quote"   = every quote equally likely
avoid_repeats = 20  # don't repeat within the last N quotes

# per-subject overrides, keyed as shown by `hyprmuse list`
[subjects."genius:342499"]
weight = 2.0
enabled = true
```

`weighting = "subject"` is the default so a 162-song band does not drown out an
author with nine quotes.

## Storage

```
~/.local/share/hyprmuse/subjects/*.json   one file per subject
~/.local/share/hyprmuse/recent.json       recently shown, for repeat avoidance
~/.config/hyprmuse/config.toml            optional settings
```

Harvested text lives outside the repository, so scraped content stays out of git.

## Development

```bash
uv run pytest               # the tests
scripts/gate origin/main    # the tests with coverage, then octoflow-ai's quality gate on
                            # the change since origin/main, as Jenkins runs it; writes quality.md
```

Opening a pull request hands it over: once Jenkins passes it, one that changes only the
package's or the tests' Python, or Markdown, merges into `main` without a human.
`docs/agents/README.md` has the exact rule and how to hold a pull request back.

A merge into `main` that raises `version` in `pyproject.toml` releases it: Jenkins builds
the binary with `packaging/build-binary.sh`, and the sdist and wheel with `uv build`, and
publishes them as release `v<version>`. The Jenkins job `hyprmuse-pypi`
(`packaging/pypi/Jenkinsfile`) then uploads the sdist and wheel to PyPI.

## License

MIT; see `LICENSE`. The release binary also bundles Python, the packages hyprmuse
depends on, and the C libraries linked into them, each under its own license; each
release carries their notices as `hyprmuse-third-party-licenses.txt`.
