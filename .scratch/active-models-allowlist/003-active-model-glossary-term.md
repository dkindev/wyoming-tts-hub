---
title: "Add `Active Model` glossary term to CONTEXT.md"
labels:
  - ready-for-agent
created: 2026-08-13
---

## What to build

Update `CONTEXT.md` to capture the runtime-allowlist concept shipped by the `active_models` setting, following the format in `.agents/skills/grill-with-docs/CONTEXT-FORMAT.md`. Keep definitions tight, one sentence, domain language only — no implementation details (no mention of config files, settings field names, or internals other than the `active_models` setting itself and the `enabled` flag, which the glossary already uses literals for).

Add under **Language**:

- **Active Model**: A **Model** that the running instance actually serves — enabled **and** listed in the instance's `active_models` allowlist. Only **Active Models**' **Voices** are advertised over the **Wyoming** protocol.
  _Avoid_: loaded model, warmed-up model

Append under **Flagged ambiguities**:

- "Active" was used overlapping with the `enabled` flag — resolved: `active_models` is a runtime allowlist filter layered on top of `enabled`; a model must be both to be served.

Do not promote "Backend" to a glossary term — that setting is dormant and an implementation detail of a future factory.

## Acceptance criteria

- [x] **Active Model** entry added under **Language** per CONTEXT-FORMAT.md (one sentence, `_Avoid_` list)
- [x] Flagged-ambiguities entry added describing the `active_models` vs `enabled` relationship
- [x] No reference to `data.yml` or other implementation details in the new entries
- [x] No new **Backend** term added

## Blocked by

- #001 — Add `active_models` runtime allowlist (end-to-end)