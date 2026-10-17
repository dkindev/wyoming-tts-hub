---
title: "Sync the domain docs guide's term roster with the glossary"
labels:
  - ready-for-human
created: 2026-10-17
---

## What to build

The domain docs guide tells exploring agents which terms the glossary defines, so
agents can reach for the right word. Its roster has drifted: it lists **SSML**,
which was never a glossary term, and it omits **VoiceNormalization**. Realign it
against the refactored glossary so the list is exactly the terms the glossary
defines.

## Acceptance criteria

- [x] The roster in the domain docs guide lists exactly the terms defined in the
      glossary, in the glossary's casing
- [x] **SSML** is no longer presented as a glossary term
- [x] **VoiceNormalization** is listed

## Blocked by

- 04-delete-non-model-sections.md