---
title: "Add ModelInfo beside Model"
labels:
  - ready-for-agent
created: 2026-10-17
---

## What to build

The domain entity a **TTS Engine** is built for gets a name that cannot be confused with the
weights it loads. `ModelInfo` becomes the canonical name of that dataclass, while `Model` stays
importable as an alias to the same class, so nothing in the repo breaks. The engine's public
accessor gains `model_info`, with `model` kept as a delegating alias, and the test helper gains
`make_model_info`, with `make_model` delegating to it.

This is the expand step of an expand-contract rename: after this ticket the new form exists
everywhere it needs to, and the migrate tickets that follow can each rename one path while the old
form still works.

## Acceptance criteria

- [x] `ModelInfo` is the canonical dataclass; `Model` is an alias to it, and importing either name
      yields the same class object
- [x] `PredefinedData.models` is annotated as a list of `ModelInfo`
- [x] `TtsEngine` exposes the entity through a `model_info` accessor; `model` remains and resolves
      to the same value
- [x] The test helpers expose `make_model_info` as the builder, with `make_model` still working
      and producing an equal value
- [x] A test pins that `Model is ModelInfo`, that both engine accessors agree, and that the two
      builders agree
- [x] No module outside the entity definition and the test helpers changes behaviour

## Blocked by

None - can start immediately.