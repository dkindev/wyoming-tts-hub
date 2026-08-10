---
title: "Align DataStorage tests to the locale-less schema"
labels:
  - ready-for-agent
created: 2026-08-10
---

## What to build

Bring `test_data_storage.py` in line with the new data model from
[#1](01-restructure-model-config-schema.md): voices carry no locale, IDs are
`{model_id}-{voice_name}`, and the model config YAML has no `locales:` nesting and no
`language:` keys.

Mechanical updates across all test classes:

- All `Voice(...)` constructions: drop the `locale=` argument, use the new IDs
  (`v5_5_ru-aidar`, `v3_en-en_0`, ...).
- All `Model(...)` constructions: drop the `language=` argument (the field no longer
  exists).
- All YAML fixture strings: un-nest `voices:` from `locales.<locale>` up to the model
  level, remove `language:` keys, keep `normalization:` / `prompts:` blocks and the
  `enabled` / `warmup` / `hash_prefix` fields.
- Assertions that used `voice.locale` as a discriminator now discriminate by
  `voice.model_id` (e.g. disabled-model filtering tests), or by voice name.
- `test_get_voices_from_all_locales` becomes `test_get_voices_from_all_models`.

No production code changes in this slice — it only codifies the new contract as tests.

## Acceptance criteria

- [x] All tests in `tests/test_data_storage.py` pass
- [x] No test constructs a `Voice` with `locale=` or a `Model` with `language=`
- [x] No YAML fixture uses the `locales:` nesting or a model `language:` key
- [x] Disabled-model filtering tests assert via `model_id`, not locale
- [x] `ruff check tests/test_data_storage.py` and `ruff format --check` pass

## Blocked by

- [#1](01-restructure-model-config-schema.md) — the schema restructure must land first
