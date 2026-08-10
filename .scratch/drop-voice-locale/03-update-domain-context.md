---
title: "Update domain context: Voice is not locale-specific"
labels:
  - ready-for-agent
created: 2026-08-10
---

## What to build

Update `CONTEXT.md` so the glossary matches the new data model: a **Voice** is a named
voice backed by a **Model** speaker and is no longer locale-specific.

Changes required:

- **Voice** term: remove the locale membership. A Voice has a unique ID (of the form
  `<model_id>-<voice_name>`), references exactly one **Model**, and maps to exactly one
  speaker. Voice IDs no longer carry a locale prefix.
- Remove **Locale** term

Keep the glossary implementation-agnostic (no file paths or class names).

## Acceptance criteria

- [x] **Voice** definition no longer states locale membership
- [x] **Locale** term has been removed
- [x] No remaining text implies a Voice carries a locale string
- [x] Glossary stays free of class names and file paths

## Blocked by

None — can start immediately.
