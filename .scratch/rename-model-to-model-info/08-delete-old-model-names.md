---
title: "Delete the old Model names"
labels:
  - ready-for-agent
created: 2026-10-17
---

## What to build

With no caller left on the old names, the aliases come out. `Model` is no longer importable, the
engine no longer answers to `model`, and the shared builder no longer answers to `make_model`.
What is left is unambiguous: no identifier in the source or the tests calls the domain entity
"model".

Names that mean something else are untouched: model ids, the `active_models` allowlist, the
predefined data's `models` collection, the `model` argument that names the LLM a prompt uses, the
model id a voice belongs to, and every operator-facing message, which still says "Model 'v5_5_ru'".

## Acceptance criteria

- [ ] The `Model` alias is gone: importing it fails, and the entity is spelled `ModelInfo`
- [ ] The engine's `model` accessor is gone: only `model_info` answers
- [ ] The shared builder's old name is gone: only `make_model_info` remains
- [ ] No remaining identifier in the source or the tests names the entity `model` or `Model`
- [ ] Model ids, the allowlist, the predefined data's `models` field, the prompt's LLM field, the
      voice's model id and every operator-facing message are unchanged
- [ ] No test references a removed name
- [ ] `ruff check`, `mypy` and `pytest` are no worse than before the change

## Blocked by

- 02 - Migrate the config path to Model Info
- 03 - Migrate the Hub path to Model Info
- 04 - Migrate the engine-construction path to Model Info
- 05 - Migrate the test doubles to Model Info
- 06 - Migrate the engine-path test modules to Model Info
- 07 - Migrate the storage- and Hub-path test modules to Model Info