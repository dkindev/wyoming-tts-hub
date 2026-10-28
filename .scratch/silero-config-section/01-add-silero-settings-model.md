---
title: "Add SileroSettings nested model to Pydantic config"
labels:
  - ready-for-agent
created: 2026-07-24
---

## What to build

Add a `SileroSettings(BaseModel)` nested model to `src/config.py` that groups the four Silero-specific settings — `sample_rate`, `models_dir`, `models_yml_url`, `models_yml_hash` — under a `silero` field on `Settings`. Move the `coerce_sample_rate` and `models_yml_hash_must_be_valid` field validators into the new model. Keep the existing flat fields on `Settings` so both access paths work during migration.

The `silero` section in `config.yml` already has these fields nested — this slice makes the Python model match.

## Acceptance criteria

- [x] `SileroSettings(BaseModel)` exists with `sample_rate: Literal[8000, 16000, 24000, 48000]`, `models_dir: str`, `models_yml_url: HttpUrl`, `models_yml_hash: str` — same defaults as current flat fields
- [x] `coerce_sample_rate` validator lives on `SileroSettings` (converts string env var to int)
- [x] `models_yml_hash_must_be_valid` validator lives on `SileroSettings` (rejects non-64-char hex)
- [x] `Settings.silero: SileroSettings` field is present
- [x] Flat `Settings.sample_rate`, `.models_dir`, `.models_yml_url`, `.models_yml_hash` still exist — no consumer code breaks
- [x] `Settings().silero.sample_rate == 48000` works
- [x] `Settings().silero.models_yml_url` parses from `config.yml` nested section
- [x] `TTS_SILERO__SAMPLE_RATE=24000` env var populates `settings.silero.sample_rate`
- [x] All existing tests pass unchanged

## Blocked by

None — can start immediately