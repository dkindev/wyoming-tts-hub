---
title: "Make active_models the only serving switch"
labels:
  - ready-for-agent
created: 2026-10-27
---

## What to build

Remove the per-Model-Info `enabled` switch from the domain model and the data file. A running instance serves exactly the Model Infos named in `active_models`, and only the Voices of those Model Infos are advertised. A missing or empty `active_models` serves no Model Infos and no Voices. An `active_models` id that is not declared in the data file still fails at startup, naming the offending ids.

The data file no longer reads `enabled`; a value left there is inert. Update the glossary's **Active Model Info** definition, the operator documentation, and the `active_models` comment so they no longer describe an `enabled AND active_models` rule.

## Acceptance criteria

- [x] A Model Info no longer carries `enabled`, and the data-file parser does not read it
- [x] Serving and Voice advertisement are decided only by `active_models`
- [x] `active_models` that is absent, null, or empty serves no Model Infos and no Voices
- [x] An `active_models` id absent from the data file fails startup, naming the unknown ids
- [x] Tests for the old disabled-model filtering are removed or rewritten to the new rule
- [x] GLOSSARY, README, and the shipped `config.yml` comment describe `active_models` as the sole switch

## Blocked by

None (can start immediately)
