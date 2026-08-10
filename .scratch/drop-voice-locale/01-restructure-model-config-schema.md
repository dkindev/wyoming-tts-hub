---
title: "Restructure model config schema: voices under models, locale-less voice IDs"
labels:
  - ready-for-agent
created: 2026-08-10
---

## What to build

The data model is moving away from locale-specific voices: a **Voice** is now just a
**Model** speaker, so the `locales:` nesting in the model configuration file and the
locale prefix in voice IDs are removed.

`YamlDataStorage` must parse the new flat shape and build locale-less voice IDs.

New YAML shape (decision from design review — do not deviate):

```yaml
models:
  v5_5_ru:
    warmup: true
    voices:
      - name: aidar
        # speaker defaults to voice name when absent or empty
      - name: henry
        speaker: en_2
        normalization: ...
```

Concretely:

- `_load_config_model` iterates `voices` directly under each model entry instead of
  the nested `locales.<locale>.voices` structure.
- Voice ID becomes `f"{model_id}-{voice_name}"` (e.g. `v5_5_ru-aidar`) — no locale prefix.
- `Voice` is constructed without a `locale` attribute (the field is gone from the dataclass).
- Model `language` stays off the dataclass; language resolution belongs to the engine's
  static model→language mapping. Do not re-add a `language` field or read a
  `language:` key from YAML.
- `warmup`/`hash_prefix`/`enabled` model fields and the `prompts:` / per-voice
  `normalization:` blocks keep their existing parsing semantics.

Migrate the application's live config file (`data/data.yml`) to the new shape so the
server still loads its voices after the parser change (the old shape would silently
produce zero voices).

This is the tracer bullet: after this slice, loading the config file end-to-end yields
locale-less Voice objects.

## Acceptance criteria

- [x] Loading `data/data.yml` yields `get_voices()` entries with IDs like `v5_5_ru-aidar` and `v3_en-henry` (no locale prefix, no `locale` attribute on `Voice`)
- [x] `get_voice("v5_5_ru-aidar")` resolves the expected Voice
- [x] `enabled: false` still excludes a model's voices; `warmup` and `hash_prefix` still parse onto the Model
- [x] `prompts` and per-voice `normalization` blocks still parse (VoiceNormalization lookup unchanged)
- [x] `data/data.yml` uses the new shape and the server loads voices from it
- [x] `pytest tests/` DataStorage-related failures do not grow beyond this file's scope

## Blocked by

None — can start immediately.
