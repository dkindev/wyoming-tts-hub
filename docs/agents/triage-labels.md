# Triage Labels

## Label Vocabulary

| Label | Meaning | Next State |
|-------|---------|------------|
| `needs-triage` | Maintainer needs to evaluate | `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix` |
| `needs-info` | Waiting on reporter for more info | `needs-triage` or `wontfix` |
| `ready-for-agent` | Fully specified, AFK-ready | `ready-for-human` (after implementation) |
| `ready-for-human` | Needs human implementation | (closed when resolved) |
| `wontfix` | Will not be actioned | (terminal) |

## Usage

When using the `triage` skill, update the `labels:` array in the issue file's frontmatter to move it through the state machine.

## Defaults

All five labels use their names as the label strings. No custom mappings required.
