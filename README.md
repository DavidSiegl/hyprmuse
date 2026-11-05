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
| `wikiquote` | quotations | authors, philosophers, scientists, films, TV, proverbs — editions `en`, `de`, `fr`, `es`, `it`, `pt`, `pl`, `ru`, `nl` | CC BY-SA |
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

Or install the `hyprmuse` package from PyPI, which needs Python 3.14 or newer.
`uv tool install` fetches that Python if the system lacks it; pipx needs it named:

```bash
uv tool install hyprmuse    # or: pipx install --python python3.14 hyprmuse
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

`--lang` selects the Wikiquote language edition: `en` (the default), `de`, `fr`, `es`,
`it`, `pt`, `pl`, `ru` or `nl`. hyprmuse knows how each of these lays out its pages, so it
keeps only the subject's own words and leaves out quotes about them or wrongly
attributed to them; another edition may work, but may mix those in. Harvesting
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

A setting of the wrong type or out of range, such as `width = "wide"` or
`lines = 0`, keeps its default, and `hyprmuse quote` names it on stderr; the
lockscreen still gets its quote. A subject file that cannot be read is skipped
the same way.

## Storage

```
~/.local/share/hyprmuse/subjects/*.json   one file per subject
~/.local/share/hyprmuse/recent.json       recently shown, for repeat avoidance
~/.config/hyprmuse/config.toml            optional settings
```

Harvested text lives outside the repository, so scraped content stays out of git.

## License

MIT; see `LICENSE`. The release binary also bundles Python, the packages hyprmuse
depends on, and the C libraries linked into them, each under its own license; each
release carries their notices as `hyprmuse-third-party-licenses.txt`.
