# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the `Status:` values tickets carry in this repo's tracker (`docs/agents/issue-tracker.md`); ticket-sync applies the same string as the GitHub issue's label.

| Label in mattpocock/skills | `Status:` value      | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), write the corresponding `Status:` value from this table.

These are the `scratch-issue-tracker` skill's values; change them there, not here.
