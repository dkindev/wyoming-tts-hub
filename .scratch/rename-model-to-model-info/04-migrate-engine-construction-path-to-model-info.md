---
title: "Migrate the engine-construction path to Model Info"
labels:
  - ready-for-agent
created: 2026-10-17
---

## What to build

Building a **TTS Engine** for a **Model Info** says so in every name it passes through: the engine
base stores and hands back `model_info`, the factory takes `model_info`, the Silero engine's
loading helpers take `model_info`, and the Engine Manager and Wyoming handler name their locals
`model_info`.

This is the batch that resolves the clash the rename exists for: in the Silero engine, the
configuration entity (`model_info`) and the weights loaded into RAM (`_loaded_model`,
`loaded_model`, the loaded package) are now told apart by name.

Renaming the Silero engine's keyword argument breaks two keyword call sites, which move in this
ticket so the suite stays green.

## Acceptance criteria

- [ ] `TtsEngine` stores the entity as `model_info` and hands it back through `model_info`
- [ ] The engine factory and the Silero engine accept and pass `model_info`
- [ ] The Silero engine's warmup and metadata helpers take `model_info`, while the loaded weights
      keep their existing names (`_loaded_model`, `loaded_model`, the loaded package)
- [ ] The Engine Manager's warmup and engine-context lookups name their **Model Info** locals
      `model_info`; the shared-engine wrapper reads the entity through `model_info`
- [ ] The Wyoming handler's local for the resolved entity is `model_info`
- [ ] The two keyword call sites that construct a Silero engine or override the factory's build
      method are updated
- [ ] `ruff check`, `mypy` and `pytest` are no worse than before the change

## Blocked by

- 01 - Add ModelInfo beside Model