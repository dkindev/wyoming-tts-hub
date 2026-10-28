---
title: "Compress glossary definitions and drop implementation detail"
labels:
  - ready-for-human
created: 2026-10-17
---

## What to build

Bring every definition in the domain glossary to one or two sentences, keeping
only what makes a term this term. Config key names stay — `engine_type`,
`ssml_supported`, `language_auto_detected`, `enabled`, `active_models` are the
concrete thing each term means, and without them **Active Model Info** has no
stated test.

Implementation mechanics come out. From **Chunk** and **Frame**: contiguity, the
memoryview rationale, views-versus-copies, and the buffer-recycling rule. From
**TTS Engine**: the clause about treating a yielded Chunk as handed over. From
**Language**: the long prose walkthrough of the auto-detect rule, which the
language now carries as relationships.

Do not change any term name except the casing fix in ticket 04, and do not
introduce new terms.

## Acceptance criteria

- [x] Every definition is one or two sentences
- [x] No definition mentions contiguity, memoryview, buffer ownership, view or
      copy semantics
- [x] **Active Model Info** still names `enabled` and `active_models`; **Model
      Info** still names `engine_type`, `ssml_supported` and
      `language_auto_detected`
- [x] **Chunk** and **Frame** remain two distinct terms, distinguished by
      provenance: a Chunk is yielded by a TTS Engine, a Frame is sliced out of a
      Chunk
- [x] Nothing defined in the glossary is dropped; only wording shrinks

## Blocked by

- 01-move-rules-to-relationships.md