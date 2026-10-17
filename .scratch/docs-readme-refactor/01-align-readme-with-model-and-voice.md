---
title: "Document the model and voice configuration the code actually reads"
labels:
  - ready-for-agent
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

- [ ] A YAML example copied out of the README loads into the data file as written
- [ ] Every documented normalization shape matches what a **VoiceNormalization**
      needs
- [ ] The `llm`/`openai` normalization type naming is consistent
- [ ] The glossary's **Model Info** and **Voice** definitions are unchanged

## Blocked by

None - can start immediately