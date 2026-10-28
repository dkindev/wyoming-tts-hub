---
title: "Align .env.example keys with the current settings"
labels:
  - ready-for-human
created: 2026-10-17
---

## What to build

`.env.example` still names settings that no longer exist, so anyone copying it
gets ignored variables. Realign every key with the settings the server actually
reads.

Known stale keys and their current homes:

- `TTS_SAMPLE_RATE` → nested under the Silero section
- `TTS_MAX_CONCURRENT_PER_MODEL` → renamed to count Sentences, not Chunks
- `TTS_MAX_CHUNK_CHARS` → renamed to Sentence
- `TTS_MODELS_YML_URL`, `TTS_MODELS_YML_HASH` → nested under the Silero section
- `TTS_NORMALIZATION__MAX_CONCURRENT_CHUNKS_PER_REQUEST` → renamed to Sentence
- `TTS_NORMALIZATION__TEXT_ENABLED` → needs the Text Format level
- `TTS_OPENAI__BASE_URL`, `TTS_OPENAI__API_KEY` → nested under normalization

## Acceptance criteria

- [x] Every key in `.env.example` resolves to a setting the server reads
- [x] No key in `.env.example` is silently ignored
- [x] Renamed keys use the domain vocabulary: Sentence, not Chunk
- [x] Defaults match the shipped defaults

## Answer

All eight stale keys are re-homed, and the template gained the keys the earlier one
never carried, so it now covers what config.yml ships.

**Every value matches the one config.yml ships**, because environment variables
outrank that file: copying the template as-is changes nothing about a deployed
server. That is what the value comparison in `tests/test_env_example.py` enforces,
so the two cannot drift apart silently.

The template had no trailing newline, so appending a key used to rewrite the last
one. It ends in a newline now, and a test reads it in a way that would notice.

Three checks guard the drift returning, each of which fails on the old file:

- every key resolves to a setting that exists (the eight that did not, fail)
- every value is the one its setting reads back, coerced the way the setting
  coerces it — enums, numbers, booleans, URLs and JSON lists included
- no key is documented twice, which the dictionary the tests read through would
  otherwise collapse into one winner and one lie

## Blocked by

None - can start immediately