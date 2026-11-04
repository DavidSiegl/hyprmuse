# Agent setup

Generated from the agent-estate template; `copier update` rewrites this file, so change the template or its answers
in `.copier-answers.yml`, not the text here. CLAUDE.md imports it.

## Issue tracker

Specs and tickets live under `.scratch/` (gitignored), mirrored two-way to GitHub Issues on DavidSiegl/hyprmuse
by ticket-sync. See `docs/agents/issue-tracker.md`.

## Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See
`docs/agents/triage-labels.md`.

## Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root, created lazily. See `docs/agents/domain.md`.

## Review gate

On: Claude's pushes of a commit with no `Verdict: pass` record under `.scratch/reviews/` are refused. Run the branch
through the `cross-review` skill before pushing. A fresh clone has the gate off until `.scratch/reviews/` is created
at its root.

## Quality gate

`scripts/gate [BASE]` runs the tests with coverage and octoflow-ai's `gate.py` over the change since BASE (default
`main`), writing `quality.md`. Run it before handing a branch to review; fix each issue it lists on changed lines, and
fix or justify each finding to weigh.

## CI and merging

Jenkins builds every pull request and `main` with the `Jenkinsfile`, running `scripts/gate` over a pull request since
its merge base and over `main` since its last successful build, and reports `continuous-integration/jenkins/pr-head`
on each pull request through its GitHub App.

Once that passes on a pull request's head commit, `.github/workflows/automerge.yml` merges it into `main` with a merge
commit and deletes its branch: opening a pull request is handing it over. To keep one for a human, open it as a draft
or label it `no-automerge`. One that changes anything but Python in the package or `tests/` and Markdown at the
root or in `docs/`, or that touches a `conftest.py`, always waits for a human, since such a file can change how CI
judged it; the header of `automerge.yml` is the rule. Never merge a pull request yourself.
