---
title: "Migrate the engine-path test modules to Model Info"
labels:
  - ready-for-agent
created: 2026-10-17
---

## What to build

The tests that cover engine construction, loading and the cache speak **Model Info** in code and
in prose: they build entities with `make_model_info`, construct `ModelInfo` directly where they
spell the class out, read the entity off an engine through `model_info`, and describe it as
**Model Info** in test names and docstrings.

## Acceptance criteria

- [ ] Every call to the shared **Model Info** builder in these modules uses its new name
- [ ] Every direct construction of the entity spells the class `ModelInfo`
- [ ] Every read of the entity off an engine goes through `model_info`
- [ ] Test names, docstrings and comments in these modules say **Model Info** where they mean the
      entity, and still say "model" where they mean a model id or the Silero weights
- [ ] Assertions on client-facing messages are unchanged
- [ ] `ruff check`, `mypy` and `pytest` are no worse than before the change

## Blocked by

- 04 - Migrate the engine-construction path to Model Info
- 05 - Migrate the test doubles to Model Info