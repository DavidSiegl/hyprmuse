# hyprmuse

## Agent skills

### Issue tracker

Specs and tickets live under `.scratch/` (gitignored), mirrored two-way to GitHub Issues on DavidSiegl/hyprmuse by
ticket-sync. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root, created lazily. See `docs/agents/domain.md`.

### Review gate

On: Claude's pushes of a commit with no `Verdict: pass` record under `.scratch/reviews/` are refused. Run the branch
through the `cross-review` skill before pushing. A fresh clone has the gate off until `.scratch/reviews/` is created
at its root.

## Quality gate

`scripts/gate [BASE]` runs the tests with coverage and octoflow-ai's `gate.py` over the change since BASE (default
`main`), writing `quality.md`. Run it before handing a branch to review; fix each issue it lists on changed lines, and
fix or justify each finding to weigh. Local only: no CI runs it.
