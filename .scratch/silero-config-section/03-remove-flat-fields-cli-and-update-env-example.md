---
title: "Remove flat silero fields, drop CLI args, update .env.example"
labels:
  - ready-for-agent
created: 2026-07-24
---

## What to build

Clean up after the migration is complete. Remove the four flat fields from `Settings` — `sample_rate`, `models_dir`, `models_yml_url`, `models_yml_hash` — since no consumers remain. Add `"silero"` to `CliArgsSource._fields_to_skip` so no `--silero_sample_rate` CLI args are generated (the silero section is env-only per `config.yml`). Update `.env.example` to use the new nested env var names.

## Acceptance criteria

- [x] Flat `sample_rate`, `models_dir`, `models_yml_url`, `models_yml_hash` removed from `Settings`
- [x] `"silero"` added to `CliArgsSource._fields_to_skip` — no `--silero_*` CLI args
- [x] `.env.example` uses `TTS_SILERO__SAMPLE_RATE`, `TTS_SILERO__MODELS_DIR`, `TTS_SILERO__MODELS_YML_URL`, `TTS_SILERO__MODELS_YML_HASH`
- [x] All tests pass

## Blocked by

- `02-migrate-consumers-to-nested-silero-access`