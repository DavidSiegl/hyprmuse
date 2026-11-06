# TODO

## Planned features

None recorded yet.

## Open issues

- **Two auto-merge runs at the same moment can still merge two raises to one version.**
  `automerge.yml` re-checks the raise right before merging (review 26, F1), which
  narrows the race to two runs that both check before either merges; the second merge
  then ships unreleased. A template issue: agent-estate's `TODO.md` holds it and what
  closes it.
- **`quote`'s `--lines`, `--width`, `--max-lines` and `--max-chars` skip `config.LEAST`.**
  `cmd_quote` copies them into `cfg` after `load_config` has checked the file, so
  `--lines 0` finds no quote even in a full library and a negative width reaches the
  wrapper. argparse could check them against `config.LEAST`. Found in review 16.
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
- **An agent's pull request can reach the PyPI token and the AUR key.** Auto-merge merges
  a pull request whatever files it changes (owner, 2026-11-05: "do the same ruling like in
  octoflow ai"), and the hyprmuse-pypi and hyprmuse-aur jobs run `packaging/pypi/` and
  `packaging/aur/` from main on the trusted node with those secrets. So an agent's pull
  request that edits them runs with the secrets once it merges. octoflow-ai has no such
  jobs. Accepted by the owner on 2026-11-05 (review 22, F1). Closed by auto-merge holding
  pull requests that change those two directories, or by the jobs reading their scripts
  from a ref only a human can move.
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
- **A Polish "see also" sub-bullet can become a quote's source.** pl.wikiquote puts
  `** Źródło: …` and `** Zobacz też: …` under a quote; when a quote has no `Źródło`,
  `wikiquote._read_bullet` takes the first sub-bullet, so `--note` shows "Zobacz też:
  …". Closed by skipping sub-bullets that only link related pages.
- **Combined bibliography headings count as the subject's own words.** The bibliography
  words in `wikiquote._NOT_THEIR_WORDS` ("notes", "références", "ссылки"…) must be the
  whole heading, since they also open titles of the subject's works ("Notes on
  Nursing"). So "Notes et références" (153 fr pages on 2026-11-05), "Notes and
  references", "Notas y referencias", "Ссылки и примечания", "Note e riferimenti" and
  "Anmerkungen und Einzelnachweise" are read. On the six live pages checked those
  sections hold only the footnote list, so nothing is stored; a page that puts bullets
  there would store them as quotes. Review 19, round 2. Closed by also matching, as a
  whole heading, two bibliography words joined by the word for "and" of each edition
  `_NOT_THEIR_WORDS` covers (en, de, fr, es, it, pt, pl, ru, nl).
- **A title ending in a suffix takes the suffix as the surname.** `wikiquote._names_subject`
  takes the title's last word outside parentheses, so for "Martin Luther King Jr." a
  heading "About King" is not recognised as about the subject, and its quotes are
  stored as the subject's own. en heads such sections "Quotes about …", which
  `_NOT_THEIR_WORDS` skips anyway. Review 19, round 2. Closed by dropping a trailing
  "Jr." or "Sr." before taking the last word. Roman numerals are not dropped: "Malcolm
  X" and "Henry VIII" would then match on a first name, which `_names_subject` rules out.
- **Narration after a sentence-ending quote becomes its source.**
  `wikiquote._split_quote_and_note` treats any text after a closing mark as the source
  when the quote ends in `.`, `!`, `?` or `…`, so `"Why would anyone do that?" he asked,
  and left.` stores "he asked, and left." as the note. The `.` case is partly by design:
  `"A sentence." Source` must keep its source. Review 19, round 2. Closed by telling
  narration ("he asked", "she said") apart from a source while keeping that case.
- **Names without a hash are moved only when their subject is next saved or removed.**
  Review 18, F4: "compatibility is attached to `save` and `remove` rather than done once",
  so `library._unhashed_file` stays in both paths, and any new write or delete path must
  remember it. Kept because a migration on load would make `hyprmuse quote`, which only
  reads, write to the library. Closed by a one-off migration that `add`, `update` and
  `remove` run before touching the store, after which `_unhashed_file` serves only it.
- **The gate's default base is main's tip, not the branch point.** Review 32, F1: CI judges a
  pull request from `git merge-base HEAD refs/remotes/origin/<target>`, but a bare
  `scripts/gate` diffs against `refs/heads/main` itself, so once main has moved on it judges
  main's newer commits as reverse edits and can disagree with CI. Also from review 32: the
  Jenkinsfile's `refs/tags/$released` borrows a reason that does not apply to tags (F2), and
  the default is stated in both `docs/agents/README.md` and the gate's header (F3). All
  agent-estate template text; closed there (a merge-base default), then taken by an update.
