---
title: "Delete Example dialogue and Flagged ambiguities from the glossary"
labels:
  - ready-for-human
created: 2026-10-17
---

## What to build

The glossary should be Language plus Relationships and nothing else. Two sections
are documentation about the model rather than the model:

- **Example dialogue** quotes configuration (`warmup: true`) and names a specific
  engine; every fact it carries is already in a definition or a relationship.
- **Flagged ambiguities** is a resolution log for "model" and "active". Those
  resolutions are already folded into the term definitions, and the glossary
  format has no place for a log.

Both sections go. No ADR is written: none of the surviving decisions is hard to
reverse, surprising without context, and the result of a real trade-off.

One casing change rides along, the only heading this refactor touches:
`Text normalization` becomes `Text Normalization`.

## Acceptance criteria

- [x] `## Example dialogue` and `## Flagged ambiguities` are gone
- [x] No fact is lost that is not already stated in a definition or relationship
- [x] `docs/adr/` is not created
- [x] `Text normalization` is now `Text Normalization`, including in any
      relationship bullets that reference it

## Blocked by

- 02-compress-definitions.md
- 03-group-language-subheadings.md