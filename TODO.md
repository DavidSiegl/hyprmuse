# TODO

## Planned features

None recorded yet.

## Open issues

- **Each source's HTTP politeness is spread over its call sites.** Now
  [#7](https://github.com/DavidSiegl/hyprmuse/issues/7).
- **Two rules decide which stored subject a token means.** Now
  [#8](https://github.com/DavidSiegl/hyprmuse/issues/8).
- **The binary bundles setuptools, which hyprmuse never imports.** PyInstaller's
  analysis of `packaging/build-binary.sh`'s build pulls in setuptools with its vendored
  packages, `packaging` and `tomli`, reached only from PyInstaller's own
  `pyi_rth_setuptools` runtime hook (the build's `xref-*.html`). They add size and a
  dozen license notices to `hyprmuse-third-party-licenses.txt`. Closed by finding what
  draws setuptools into the analysis and excluding it, then checking the binary still
  passes its smoke test.
