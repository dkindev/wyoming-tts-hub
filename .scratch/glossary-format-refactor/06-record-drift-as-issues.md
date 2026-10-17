---
title: "Record code and README drift found while refactoring the glossary"
labels:
  - ready-for-human
created: 2026-10-17
---

## What to build

Refactoring the glossary surfaced disagreement between the domain model, the code
and the README. The refactor deliberately kept the model and excluded
implementation, so the drift needs tickets of its own rather than silent edits to
the glossary. File each as a separate issue, one per drift, each with enough
detail to act on:

- **Environment example is stale** — every key in `.env.example` names a setting
  that no longer exists: `TTS_SAMPLE_RATE`, `TTS_MAX_CONCURRENT_PER_MODEL`,
  `TTS_MAX_CHUNK_CHARS`, `TTS_MODELS_YML_URL`, `TTS_MODELS_YML_HASH`,
  `TTS_NORMALIZATION__MAX_CONCURRENT_CHUNKS_PER_REQUEST`,
  `TTS_NORMALIZATION__TEXT_ENABLED`, `TTS_OPENAI__*`.
- **README documents configuration the code does not read** — `language:` and
  `locales:` per model where the code reads `languages:` and a flat `voices:`
  list; a voice id form the code does not derive; a `llm` normalization type where
  the enum is `openai`; and a normalization shape without the language level the
  code requires.
- **Sentence splitting is misspelled throughout** — the sentenizer types, module
  names and factory are all spelled without the second `c`.
- **Text Formats are never advertised** — the glossary says the server advertises
  per-Model Info Text Formats over the Wyoming protocol; the advertised payload
  carries Voices and Languages only.
- **Deprecated naming left behind** — a benchmark script at the repo root still
  uses retired names, including a cache class that no longer exists.

## Acceptance criteria

- [x] One issue filed per drift, each naming the domain term it touches
- [x] Each issue states whether the glossary, the code or the README is the thing
      that is wrong, as far as that is known
- [x] No code or README is changed by this ticket

Filed as:

- `.scratch/docs-env-example/01-align-env-example-with-settings.md`
- `.scratch/docs-readme-refactor/01-align-readme-with-model-and-voice.md`
- `.scratch/rename-chunk-to-sentence/06-fix-sentenizer-spelling.md`
- `.scratch/glossary-format-refactor/07-decide-text-format-advertisement.md`
- `.scratch/glossary-format-refactor/08-align-benchmark-with-vocabulary.md`

## Blocked by

None - can start immediately