# hyprmuse

@docs/agents/README.md

## Releases

`docs/agents/README.md`, "Releases", is the rule; here, a release also goes to PyPI and the AUR (the hyprmuse-pypi
and hyprmuse-aur jobs, `packaging/pypi/` and `packaging/aur/`), and `scripts/package` builds the Linux binary it
attaches. Released paths include the `hyprmuse` package, `quote.py`, the lockfile and the rest of `packaging/`. A
`major` bump is a change that breaks existing flags, exit codes, the stored library or `config.toml`.

One change needs no raise although it reaches users: one to the AUR package's own PKGBUILD alone, which the
hyprmuse-aur job publishes for the latest release, but only once the pull request itself has moved the PKGBUILD to
that release and raised `pkgrel` (`packaging/aur/publish.sh`'s header says how; `.release-exempt` lists it).
