---
title: "Key server-wide normalization prompts by Language, not by locale"
labels:
  - ready-for-agent
created: 2026-10-18
---

## What to build

An operator who configures LLM-based text normalization the way the shipped
configuration is written gets no LLM normalization at all, and no error to tell
them so.

The server-wide normalization prompts are keyed by locale, but the key the
normalizer looks them up by is the **Language** the request resolved to — the
bare code the Model Info declares. A Model Info declaring `ru` can never select a
prompt stored under `ru_RU`, because the locale form is also refused as a request
language outright. The shipped Russian prompt is therefore unreachable, and the
same silent no-op will hit every prompt an operator adds.

Re-key the server-wide prompts by the bare **Language** code, matching the way
per-voice normalization overrides are already keyed in the data file. An
operator writing `ru` gets the prompt they wrote.

While in that code path, the normalizer cache is keyed by language, text format
and normalization type, but only the default entries are ever registered under
those keys — so every per-language lookup misses and silently falls back to the
default normalizer. Fix the registration so the key it looks up is the key it
stored, and cover both.

## Acceptance criteria

- [ ] A server-wide prompt keyed by a Model Info's declared Language is selected
      for that Language
- [ ] A prompt keyed by a locale form such as `ru_RU` is not consulted for a
      request resolving to `ru`, because no request can resolve to it
- [ ] The shipped Russian prompt is reachable, given the rest of the shipped
      configuration
- [ ] A missing prompt for a Language still falls back to the default
      normalizer rather than failing the request
- [ ] A normalizer built for a specific Language and text format is reused from
      the cache instead of being rebuilt on every request
- [ ] Tests cover the Language-keyed lookup, the fallback, and cache reuse
- [ ] The shipped configuration and `.env.example` are updated together, and
      stay consistent with each other

## Blocked by

None (can start immediately).