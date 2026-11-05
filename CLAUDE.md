# hyprmuse

@docs/agents/README.md

## Releases

A merge into `main` releases the version in `pyproject.toml` as GitHub release `v<version>`, and to PyPI and the
AUR, if that release doesn't exist yet (Jenkinsfile, Release stage). A change reaches users only if it raises the
version, except one to the AUR package's own PKGBUILD alone: the hyprmuse-aur job publishes that for the latest
release, but only once the pull request itself has moved the PKGBUILD to that release and raised `pkgrel`
(`packaging/aur/publish.sh`'s header says how). Two pull requests open at once can each pass with the same raise; the one merged
second then ships unreleased (`TODO.md`).

- Every change that reaches users (the `hyprmuse` package, `quote.py`, the lockfile, packaging: any path
  `scripts/version-raised.sh` does not exempt) raises the version in the same pull request, and every spec or
  ticket for one lists the bump and its level as an acceptance criterion: `uv version --bump patch` for a fix,
  `minor` for a new feature or flag, `major` for a change that breaks existing flags, exit codes, the stored
  library or `config.toml`.
- Changes only to docs, tests, CI or repository tooling don't bump the version; Jenkins's Version stage lets them
  through without a raise (`scripts/version-raised.sh` lists which paths count as such).
- Bump with `uv version --bump <level>`, never by editing `pyproject.toml`: it also updates `uv.lock`.
- Don't create tags or releases by hand; Jenkins does that after the merge.
