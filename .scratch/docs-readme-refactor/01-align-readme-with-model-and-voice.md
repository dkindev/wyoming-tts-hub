---
title: "Document the model and voice configuration the code actually reads"
labels:
  - ready-for-human
created: 2026-10-17
---

## What to build

README's model and voice sections document a configuration shape the server no
longer reads, so following the README produces data that is silently dropped.
Realign the documented shape with what a **Model Info** and a **Voice** actually
carry.

Drift to resolve:

- Per-model `language:` and `locales:` where the code reads `languages:` and a
  flat `voices:` list
- A voice id form the code does not derive — the code derives
  `<model id>-<voice name>`
- A `llm` normalization type where the enum value is `openai`
- A normalization shape with no **Language** level, while the code requires one
  per Voice, per **Text Format**, per **Language**
- Model keys the README never mentions: `engine_type`, `ssml_supported`,
  `language_auto_detected`, `warmup`, `hash_prefix`, and the reference audio,
  reference text and instruction parameters for cloning-style **Voices**

Decide per item whether the README is wrong or the code is. If the code is wrong,
the fix is out of scope here — file it separately rather than weakening the
**Model Info** and **Voice** definitions in the glossary.

## Acceptance criteria

- [x] A YAML example copied out of the README loads into the data file as written
- [x] Every documented normalization shape matches what a **VoiceNormalization**
      needs
- [x] The `llm`/`openai` normalization type naming is consistent
- [x] The glossary's **Model Info** and **Voice** definitions are unchanged

## Answer

Every item in the drift list turned out to be the README's fault, so no code changed.
The README now documents `languages:` and a flat `voices:` list, derives a voice id as
`<model id>-<voice name>`, spells the LLM type `openai`, and keys a normalization
override by language and then by text format. `engine_type`, `ssml_supported`,
`language_auto_detected` and `hash_prefix` are documented, as are the cloning-style
voice parameters — marked as read but not yet consumed by any engine, which is
exactly what they are.

`enabled` is documented together with `active_models`, because neither switch implies
the other and a model with both off is simply not served.

**Tests keep it that way.** Every fenced yaml example is loaded through the real
storage, and the field tables are checked against the shapes: a documented key no
shape has, or a normalization key naming no Text Format, fails. The last one matters
because such a key is dropped in silence — an override the reader wrote and the server
never reads. I wrote such a row into the first draft of this fix and the test caught
it.

Two code defects the rewrite exposed are filed separately rather than fixed here:
`.scratch/docs-readme-refactor/02-fix-data-storage-input-rejections.md` covers a
`Path` that the storage's own type hint invites and `speaker: null`, both of which
crash on the way in.

## Blocked by

None - can start immediately