---
title: "Migrate the config path to Model Info"
labels:
  - ready-for-agent
created: 2026-10-17
---

## What to build

Reading the data file end to end speaks **Model Info**. The Data Storage builds `ModelInfo` values
out of the YAML, advertises them in its types, and names them that way in its docstrings and its
own code. The names of the storage's accessors (`get_model_info`, `get_model_infos`) and the
ids they are keyed by do not change - only the entity's name does.

## Acceptance criteria

- [ ] The Data Storage constructs `ModelInfo` from each YAML entry and no longer names the entity
      `Model` in code
- [ ] The storage interface and implementation annotate the single-model and all-models accessors
      as returning `ModelInfo`
- [ ] Local names that hold one **Model Info** are `model_info`; ids (`model_id`), plural
      collections (`models`, `served_models`) and the `active_models` allowlist keep their names
- [ ] Docstrings and comments in this path say **Model Info**, not **Model**
- [ ] `ruff check`, `mypy` and `pytest` are no worse than before the change

## Blocked by

- 01 - Add ModelInfo beside Model