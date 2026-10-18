---
title: "Migrate the test doubles to Model Info"
labels:
  - ready-for-agent
created: 2026-10-17
---

## What to build

The shared test doubles speak **Model Info**, so every later test-module migration is a
mechanical call-site sweep. `make_model_info` is the builder; the fake engine, fake factory and
fake storage take and annotate `ModelInfo` and `model_info`.

## Acceptance criteria

- [x] The fake engine takes the entity as `model_info` and passes it to its base
- [x] The fake engine factory takes `model_info` and records the id off it
- [x] The fake storage annotates its single-model and all-models accessors with `ModelInfo`
- [x] Every helper that reads the entity off an engine reads `model_info`
- [x] Docstrings in the helpers say **Model Info**, not **Model**
- [x] No test module outside the helpers changes in this ticket
- [x] `ruff check`, `mypy` and `pytest` are no worse than before the change

## Blocked by

- 01 - Add ModelInfo beside Model