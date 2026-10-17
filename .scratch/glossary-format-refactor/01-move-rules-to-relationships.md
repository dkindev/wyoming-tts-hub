---
title: "Move behavioural rules out of glossary definitions into Relationships"
labels:
  - ready-for-human
created: 2026-10-17
---

## What to build

Every term definition in the domain glossary currently mixes two things: what the
term is, and what the system does with it. Split them. Definitions say what a
thing is; `## Relationships` carries the rules.

Rules to relocate, phrased as relationships rather than as behaviour:

- **Language**: a Language sent by a client is validated against the selected
  **Model Info**'s declared Languages and the request refused on a mismatch; an
  omitted Language is filled in from the **Model Info**'s sole declared Language
  when it declares exactly one and does not auto-detect; a **Model Info** that
  declares several Languages and does not auto-detect cannot be served a request
  carrying none, and the refusal names it and every declared Language.
- **Sentence**: the **TTS Engine Hub** splits text into Sentences to stay within
  the configured sentence length limit. Drop "model length limits" — there is no
  per-model limit in the model.
- **Frame**: sized by the configured frame duration.
- **Chunk**: yielding a Chunk hands it over — see ticket 02, this one keeps the
  rule in domain words only.
- **VoiceNormalization**: when present it overrides the server-wide default for
  its Voice, **Text Format** and **Language**.
- **Active Model Info**: enabled and listed in the instance allowlist, and only
  its Voices are advertised over the Wyoming protocol.
- **Model Info**: its declared Languages are the source of truth advertised for
  its Voices.
- **TTS Engine Hub**: coordinates warmup and shutdown across **TTS Engines**.

## Acceptance criteria

- [x] No definition under `## Language` states a rule; each definition only says
      what its term is
- [x] Every rule listed in this issue appears as a relationship bullet, with no
      information lost
- [x] No relationship bullet restates a definition that already says it
- [x] Term names and their `_Avoid_` lines are unchanged

## Blocked by

None - can start immediately