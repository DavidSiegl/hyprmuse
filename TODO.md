# TODO

## Planned features

None recorded yet.

## Open issues

- **Each source's HTTP politeness is spread over its call sites.** Now
  [#7](https://github.com/DavidSiegl/hyprmuse/issues/7).
- **Two rules decide which stored subject a token means.** Now
  [#8](https://github.com/DavidSiegl/hyprmuse/issues/8).
- **The binary's notices leave out its C libraries.** `packaging/third_party_notices.py`
  collects the license files Python and each bundled package ship, but lxml's wheel links
  libxml2, libxslt and zlib statically, and uv's Python build brings OpenSSL, libffi and
  others, none of which ship a license file there. Their MIT, BSD and Apache notices are
  missing from `hyprmuse-third-party-licenses.txt`. Closed by finding each library's
  notice for the versions bundled (python-build-standalone and the lxml wheel builds
  record them) and adding it to the notices.
- **The binary bundles setuptools, which hyprmuse never imports.** PyInstaller's
  analysis of `packaging/build-binary.sh`'s build pulls in setuptools with its vendored
  packages, `packaging` and `tomli`, reached only from PyInstaller's own
  `pyi_rth_setuptools` runtime hook (the build's `xref-*.html`). They add size and a
  dozen license notices to `hyprmuse-third-party-licenses.txt`. Closed by finding what
  draws setuptools into the analysis and excluding it, then checking the binary still
  passes its smoke test.
