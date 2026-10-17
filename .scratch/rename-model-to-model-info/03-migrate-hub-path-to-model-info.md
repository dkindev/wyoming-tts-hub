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

- [ ] The synthesis context takes a `ModelInfo` and exposes it as `model_info`
- [ ] The Hub's Language validation resolves the **Model Info** off the context and phrases its
      declared **Languages** from it
- [ ] Language-resolving middleware reads the **Model Info** off the context
- [ ] No local name in this path calls the entity `model`
- [ ] Every error message and log line in this path keeps its current wording
- [ ] `ruff check`, `mypy` and `pytest` are no worse than before the change

## Blocked by

- 01 - Add ModelInfo beside Model