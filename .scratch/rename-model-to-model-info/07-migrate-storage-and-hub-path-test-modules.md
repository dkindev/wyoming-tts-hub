---
title: "Migrate the storage- and Hub-path test modules to Model Info"
labels:
  - ready-for-agent
created: 2026-10-17
---

## What to build

The tests that cover the data file, the Hub, the Wyoming handler and the middleware chain speak
**Model Info** in code and in prose: they build entities with `make_model_info`, construct
`ModelInfo` directly where they spell the class out, and describe the entity as **Model Info** in
test names and docstrings. Lowercase "model" prose that means a model id or a Silero model stays
as it is.

## Acceptance criteria

- [ ] Every call to the shared **Model Info** builder in these modules uses its new name
- [ ] Every direct construction of the entity spells the class `ModelInfo`
- [ ] The tests for the entity's own dataclass name it `ModelInfo` throughout
- [ ] Test names, docstrings and comments in these modules say **Model Info** where they mean the
      entity, and still say "model" where they mean a model id
- [ ] Assertions on client-facing messages are unchanged
- [ ] `ruff check`, `mypy` and `pytest` are no worse than before the change

## Blocked by

- 02 - Migrate the config path to Model Info
- 03 - Migrate the Hub path to Model Info
- 05 - Migrate the test doubles to Model Info