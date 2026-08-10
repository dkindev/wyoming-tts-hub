---
title: "Derive voice IDs from model-speaker pairs and cover reference fields"
labels:
  - ready-for-human
created: 2026-08-10
---

## What to build

A Voice is defined as the model↔speaker mapping, so its ID is derived from the
speaker rather than the voice name: `{model_id}-{speaker}` instead of
`{model_id}-{voice_name}`.

`YamlDataStorage` builds voice IDs as `f"{model_id}-{speaker}"`. The existing
defaulting stays unchanged: when a voice omits or empties `speaker`, it defaults
to the voice name, so IDs only change for voices that declare a speaker distinct
from their name. `name` remains a required human-readable label on the Voice.

Update the DataStorage tests:
- the locale-less schema test must expect the speaker-based ID for a voice with
  a distinct speaker (e.g. a `henry` voice with `speaker: en_2` under `v3_en`
  becomes `v3_en-en_2`, and its lookup uses that ID),
- add coverage that `ref_audio`, `ref_text`, and `instruct` keys in a voice's
  YAML entry parse onto the Voice.

Update the **Voice** term in `CONTEXT.md`: the unique ID form becomes
`<model_id>-<speaker>`, and Voice is framed as the model-speaker mapping with
`name` as the human-readable label.

## Acceptance criteria

- [x] Voice IDs are constructed as `{model_id}-{speaker}`
- [x] `name` remains a required label; `speaker` still defaults to the voice name when absent or empty
- [x] Locale-less schema test asserts the speaker-based ID and its lookup (e.g. `v3_en-en_2`)
- [x] New test: YAML `ref_audio` / `ref_text` / `instruct` keys populate the Voice
- [x] CONTEXT.md Voice term documents the `<model_id>-<speaker>` ID and the model-speaker mapping framing

## Blocked by

None - can start immediately
