---
title: "Migrate the Hub path to Model Info"
labels:
  - ready-for-agent
created: 2026-10-17
---

## What to build

A synthesis request carries a **Model Info** all the way through the Hub. The synthesis context
exposes it as `model_info`, the Hub reads the **Model Info** it resolved for the requested
**Voice**, and Language resolution and validation consult it. Client-facing error messages are
unchanged: the client still hears `model 'v5_5_ru'`.

## Acceptance criteria

- [x] The synthesis context takes a `ModelInfo` and exposes it as `model_info`
- [x] The Hub's Language validation resolves the **Model Info** off the context and phrases its
      declared **Languages** from it
- [x] Language-resolving middleware reads the **Model Info** off the context
- [x] No local name in this path calls the entity `model`
- [x] Every error message and log line in this path keeps its current wording
- [x] `ruff check`, `mypy` and `pytest` are no worse than before the change

## Blocked by

- 01 - Add ModelInfo beside Model