---
title: "Group glossary terms under subheadings"
labels:
  - ready-for-human
created: 2026-10-17
---

## What to build

Give the domain glossary's `## Language` section natural clusters, so a reader
can find a term without scanning the whole list. Proposed grouping, all term
names unchanged:

- **Engines and models** — TTS Engine Hub, TTS Engine, Model Info, Active Model Info
- **Voices** — Speaker, Voice, VoiceNormalization, Prompt
- **Language and text** — Language, Text Format, Text normalization
- **Synthesis pipeline** — Sentence
- **Audio** — Chunk, Frame

Also trim the context intro at the top of the file so it states what the context
is and why it exists in two sentences, rather than repeating the project
description.

## Acceptance criteria

- [x] `## Language` has the five subheadings above
- [x] All 14 terms are present, each exactly once, with its `_Avoid_` line intact
- [x] No term is renamed, added, or removed by this ticket
- [x] The context intro is at most two sentences

## Blocked by

None - can start immediately