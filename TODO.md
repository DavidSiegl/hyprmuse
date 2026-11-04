# TODO

## Planned features

None recorded yet.

## Open issues

- **Each source's HTTP politeness is spread over its call sites.** Now
  [#7](https://github.com/DavidSiegl/hyprmuse/issues/7).
- **Two rules decide which stored subject a token means.** Now
  [#8](https://github.com/DavidSiegl/hyprmuse/issues/8).
- **`packaging/pypi/publish.sh` has no committed test.** It was checked by hand against
  GitHub's real v0.3.1 and a local pypiserver index: an upload, a rerun that stops
  before building, an index missing one file, and a tag whose commit is not on main. A
  committed test needs stand-ins for GitHub's `releases/latest` redirect and the origin
  remote, and must run offline in `scripts/gate`.
- **The AUR and PyPI publish jobs repeat each other.** `packaging/pypi/` copies
  `packaging/aur/`'s pattern (on the `aur-jenkins` branch, PR #22): the latest-release
  lookup in each `publish.sh`, and each Jenkinsfile's trusted-node setup, triggers and
  options. Kept apart so each channel's job is set up and fails on its own, since the AUR
  waits for its registration to reopen. Closed by a shared lookup under `packaging/`
  once both are on main, or by one job with a stage per channel, if a third channel
  comes.
- **The agents' GitHub token can create releases and attach files to them.** Review 09,
  F1: "anyone who can create a release can publish". `packaging/pypi/publish.sh` no
  longer trusts release files: it builds the tag itself after checking that the tag is on
  main. Still exposed: the binary that the README's Setup downloads from
  `releases/latest`, and `packaging/aur/publish.sh` (PR #22), which packages that binary
  and checks it only against the `.sha256` beside it, in the same release. An agent could
  replace both, or make its own release latest. Closed by giving the Release stage a token
  of its own that agents never hold, and taking release write access from the agents'
  token; or by having the trusted node check each asset against a hash that a
  reviewed commit records.
- **The binary bundles setuptools, which hyprmuse never imports.** PyInstaller's
  analysis of `packaging/build-binary.sh`'s build pulls in setuptools with its vendored
  packages, `packaging` and `tomli`, reached only from PyInstaller's own
  `pyi_rth_setuptools` runtime hook (the build's `xref-*.html`). They add size and a
  dozen license notices to `hyprmuse-third-party-licenses.txt`. Closed by finding what
  draws setuptools into the analysis and excluding it, then checking the binary still
  passes its smoke test.
