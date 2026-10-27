---
title: "Add warmup_models and derive Model Info warmup in storage"
labels:
  - ready-for-agent
created: 2026-10-27
---

## What to build

Move warmup selection out of the data file and into the instance configuration. Add a `warmup_models` list to the settings, wired through YAML, environment, and repeated CLI flags. The data file no longer reads `warmup`; a value left there is inert.

For data loaded from a YAML file, a served Model Info is marked for warmup exactly when its id is listed in `warmup_models`. An id in `warmup_models` that is not declared in the data file fails startup, naming the unknown ids. A declared id that is not in `active_models` cannot be served, so it logs a warning and is skipped. A directly supplied `PredefinedData` keeps the warmup values already on its Model Infos; the config list does not override them.

The shipped configuration lists the currently preloaded Model Info so startup behavior is preserved. Update the operator documentation and the glossary's warmup relationship.

## Acceptance criteria

- [x] Settings expose `warmup_models` as a list; absent or null resolves to an empty list
- [x] YAML, environment, and repeated CLI flags all populate `warmup_models`
- [x] Data-file `warmup` is no longer read
- [x] YAML-loaded Model Infos have `warmup` derived from `warmup_models`
- [x] Unknown `warmup_models` ids fail startup, naming the unknown ids
- [x] A declared-but-inactive warmup id logs a warning and does not fail startup
- [x] A directly supplied `PredefinedData` preserves its own warmup values
- [x] The shipped configuration preserves today's startup warmup behavior
- [x] Tests cover config wiring, derivation, unknown ids, inactive ids, and direct `PredefinedData`
- [x] README, GLOSSARY, and `.env.example` describe `warmup_models`

## Blocked by

- 01 — Make active_models the only serving switch
