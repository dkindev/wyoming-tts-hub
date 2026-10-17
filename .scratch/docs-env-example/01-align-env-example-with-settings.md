---
title: "Align .env.example keys with the current settings"
labels:
  - ready-for-agent
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

- [ ] Every key in `.env.example` resolves to a setting the server reads
- [ ] No key in `.env.example` is silently ignored
- [ ] Renamed keys use the domain vocabulary: Sentence, not Chunk
- [ ] Defaults match the shipped defaults

## Blocked by

None - can start immediately