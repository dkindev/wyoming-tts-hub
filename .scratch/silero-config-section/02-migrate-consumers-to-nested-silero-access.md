---
title: "Migrate consumers to nested silero config access"
labels:
  - ready-for-agent
created: 2026-07-24
---

## What to build

Update all code that reads the four Silero settings from the flat `Settings` fields to read from the nested `Settings.silero.*` path instead. This covers the dependency-wiring layer and test assertions.

Files to touch:
- `src/main.py` — `create_engine()` constructs `TTSConfig` using `settings.silero.sample_rate`, `.models_dir`, `.models_yml_url`, `.models_yml_hash`
- `tests/test_config.py` — update `test_config_yml_overrides_defaults` assertion from `settings.sample_rate` to `settings.silero.sample_rate`
- `tests/test_tts_models.py` — update `test_tts_config_accepts_models_yml_url_and_hash` references from `settings.models_yml_url`/`.models_yml_hash` to `settings.silero.models_yml_url`/`.models_yml_hash`

No behavioral changes — the same values flow through, just from a different access path.

## Acceptance criteria

- [x] `create_engine()` in `main.py` reads all four settings from `settings.silero.*`
- [x] `test_config_yml_overrides_defaults` asserts on `settings.silero.sample_rate`
- [x] `test_tts_config_accepts_models_yml_url_and_hash` asserts on `settings.silero.models_yml_url` and `.models_yml_hash`
- [x] All tests pass

## Blocked by

- `01-add-silero-settings-model`