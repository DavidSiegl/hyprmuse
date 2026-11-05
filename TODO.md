# TODO

## Planned features

None recorded yet.

## Open issues

- **`quote`'s `--lines`, `--width`, `--max-lines` and `--max-chars` skip `config.LEAST`.**
  `cmd_quote` copies them into `cfg` after `load_config` has checked the file, so
  `--lines 0` still prints "No quotes stored yet" and a negative width reaches the
  wrapper. argparse could check them against `config.LEAST`. Found in review 16.
- **Two rules decide which stored subject a token means.** Now
  [#8](https://github.com/DavidSiegl/hyprmuse/issues/8).
- **Neither `publish.sh` has a committed test.** Review 08, F6: "the bare-repository
  acceptance is not committed or run anywhere"; a wrong branch choice (review 08, F1)
  went unnoticed for that reason. `packaging/aur/publish.sh` was checked by hand against a
  local bare repository standing in for the AUR; `packaging/pypi/publish.sh` against
  GitHub's real v0.3.1 and a local pypiserver index: an upload, a rerun that stops before
  building, an index missing one file, and a tag whose commit is not on main. A committed
  test has to run offline, so it needs stand-ins for GitHub's `releases/latest` redirect,
  the origin remote and the asset downloads that `update.sh` makes. Closed by tests, run
  by `scripts/gate`, that drive each `publish.sh` against those stand-ins and a bare
  repository or local index.
- **The AUR and PyPI publish jobs repeat each other.** `packaging/pypi/` copies
  `packaging/aur/`'s pattern: the latest-release lookup in each `publish.sh`, and each
  Jenkinsfile's trusted-node setup, triggers and options. Kept apart so each channel's job
  is set up and fails on its own. Closed by a shared lookup under `packaging/`, or by one
  job with a stage per channel, if a third channel comes.
- **The agents' GitHub token can create releases and attach files to them.** Review 09,
  F1: "anyone who can create a release can publish". `packaging/pypi/publish.sh` no
  longer trusts release files: it builds the tag itself after checking that the tag is on
  main. Still exposed: the binary that the README's Setup downloads from
  `releases/latest`, and `packaging/aur/publish.sh`, which packages that binary and checks
  it only against the `.sha256` beside it, in the same release. An agent could replace
  both, or make its own release latest. Closed by giving the Release stage a token of its
  own that agents never hold, and taking release write access from the agents' token; or
  by having the trusted node check each asset against a hash that a reviewed commit
  records.
- **The binary bundles setuptools, which hyprmuse never imports.** PyInstaller's
  analysis of `packaging/build-binary.sh`'s build pulls in setuptools with its vendored
  packages, `packaging` and `tomli`, reached only from PyInstaller's own
  `pyi_rth_setuptools` runtime hook (the build's `xref-*.html`). They add size and a
  dozen license notices to `hyprmuse-third-party-licenses.txt`. Closed by finding what
  draws setuptools into the analysis and excluding it, then checking the binary still
  passes its smoke test.
- **Names without a hash are moved only when their subject is next saved or removed.**
  Review 18, F4: "compatibility is attached to `save` and `remove` rather than done once",
  so `library._unhashed_file` stays in both paths, and any new write or delete path must
  remember it. Kept because a migration on load would make `hyprmuse quote`, which only
  reads, write to the library. Closed by a one-off migration that `add`, `update` and
  `remove` run before touching the store, after which `_unhashed_file` serves only it.
