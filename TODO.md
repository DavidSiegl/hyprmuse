# TODO

## Planned features

None recorded yet.

## Open issues

- **Each source's HTTP politeness is spread over its call sites.** Every call
  to `sources/base.py:get` repeats `key=` and `throttle=`, and the throttle
  state is the module-global `_LAST_CALL`. `Genius._lyrics` calls `get` with
  no throttle and relies on the `time.sleep` in `Genius.fetch` instead. Tests
  swap `get` per module for a lambda that ignores the URL, so no test can
  check what was requested; Genius pagination (`Genius._songs`) and
  Gutenberg's three-URL fallback (`Gutenberg.fetch`) are untested. Closed by
  giving each source one client that holds its throttle and key, passed in
  rather than imported, with a fake for tests that records requests and
  answers them by URL.
- **Two rules decide which stored subject a token means.** `library.find`
  prefers an exact `source:id` match and otherwise matches a name substring;
  `lockscreen._candidates` takes a name substring *or* an exact key. So
  `hyprmuse remove foo` and `hyprmuse quote --subject foo` can disagree. The
  per-subject config lookup (`cfg["subjects"][subject_key(...)]`) is repeated
  in `lockscreen._candidates` and `lockscreen._weight`, and callers in
  `cli.py` build `library.subject_key` themselves. Closed by one lookup rule
  in `library` and a key owned by `Subject`.
