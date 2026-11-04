# TODO

## Planned features

None recorded yet.

## Open issues

- **Each source's HTTP politeness is spread over its call sites.** Now
  [#7](https://github.com/DavidSiegl/hyprmuse/issues/7).
- **Two rules decide which stored subject a token means.** Now
  [#8](https://github.com/DavidSiegl/hyprmuse/issues/8).
- **`packaging/pypi/publish.sh` has no committed test.** It was checked by hand against
  a stand-in for GitHub's release redirect and downloads, and a local pypiserver index
  (upload, a rerun that skips, a hash mismatch, a release with one file or neither). A
  committed test needs those two stand-ins and must run offline in `scripts/gate`.
- **The AUR and PyPI publish jobs repeat each other.** `packaging/pypi/` copies
  `packaging/aur/`'s pattern (on the `aur-jenkins` branch, PR #22): the latest-release
  lookup in each `publish.sh`, and each Jenkinsfile's trusted-node setup, triggers and
  options. Kept apart so each channel's job is set up and fails on its own, since the AUR
  waits for its registration to reopen. Closed by a shared lookup under `packaging/`
  once both are on main, or by one job with a stage per channel, if a third channel
  comes.
- **The binary bundles setuptools, which hyprmuse never imports.** PyInstaller's
  analysis of `packaging/build-binary.sh`'s build pulls in setuptools with its vendored
  packages, `packaging` and `tomli`, reached only from PyInstaller's own
  `pyi_rth_setuptools` runtime hook (the build's `xref-*.html`). They add size and a
  dozen license notices to `hyprmuse-third-party-licenses.txt`. Closed by finding what
  draws setuptools into the analysis and excluding it, then checking the binary still
  passes its smoke test.
