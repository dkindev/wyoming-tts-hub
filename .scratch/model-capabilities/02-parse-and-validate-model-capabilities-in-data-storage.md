---
title: "Parse and validate Model capabilities in DataStorage"
labels:
  - ready-for-agent
created: 2026-08-13
---

## What to build

Parse the new **Model** capability fields from the model configuration file and
validate them at startup, mirroring the existing "reject duplicate voice IDs"
fail-fast check. The declared `languages` of a **Model** are the source of truth
the **TTS Engine Hub** will advertise for every **Voice** of the **Model**, so
they must be present.

Behavior:

- `engine_type` is required; map the YAML name (`silero`/`qwen`/`openai`) to the
  `EngineType` enum and raise `ValueError` on an unknown value.
- `languages` is required and must be non-empty; raise `ValueError` at load when
  missing or empty.
- `ssml_supported` and `language_auto_detected` parse with their documented
  defaults (`false`).

Update the sample model configuration so the Silero models declare their
capabilities (`engine_type: silero`, `languages: [ru]` / `[en]`,
`ssml_supported: true`, `language_auto_detected: true`). Extend the DataStorage
tests to cover parsing of all four new fields, their defaults, and the two
startup validation errors.

## Acceptance criteria

- [x] YAML `engine_type: silero` parses to `EngineType.SILERO`; unknown values raise `ValueError`
- [x] `languages` parses as a list of trimmed strings
- [x] Missing or empty `languages` raises `ValueError` at load
- [x] `ssml_supported` and `language_auto_detected` default to `false` when omitted
- [x] `data/data.yml` declares `engine_type`, `languages`, `ssml_supported`, `language_auto_detected` on `v5_5_ru` and `v3_en`
- [x] DataStorage tests cover new-field parsing and both validation errors

## Blocked by

- model-capabilities/01-add-engine-type-and-language-capabilities-to-model
