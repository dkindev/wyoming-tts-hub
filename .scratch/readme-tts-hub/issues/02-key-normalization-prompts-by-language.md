---
title: "Key server-wide normalization prompts by Language, not by locale"
labels:
  - ready-for-agent
created: 2026-10-18
---

Status: done

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

- [x] A server-wide prompt keyed by a Model Info's declared Language is selected
      for that Language
- [x] A prompt keyed by a locale form such as `ru_RU` is not consulted for a
      request resolving to `ru`, because no request can resolve to it
- [x] The shipped Russian prompt is reachable, given the rest of the shipped
      configuration
- [x] A missing prompt for a Language still falls back to the default
      normalizer rather than failing the request
- [x] A normalizer built for a specific Language and text format is reused from
      the cache instead of being rebuilt on every request
- [x] Tests cover the Language-keyed lookup, the fallback, and cache reuse
- [x] The shipped configuration and `.env.example` are updated together, and
      stay consistent with each other

## Blocked by

None (can start immediately).

## Answer

The shipped prompt is re-keyed from `ru_RU` to `ru`, and a miss is now logged
rather than passing for a Voice that needs no normalization.

The builder lookup is gone rather than repaired: it asked for a
`{language}__{format}__{type}` key that nothing ever registered, so every lookup
fell through to the `default__*` one. The registry is now keyed by what it
actually varies on — Text Format and normalization type — and the dead
Language-prefixed branch with it.

Normalizers are memoized per Voice, Text Format and Language. The Voice is in
that key because an LLM-backed normalizer embeds that Voice's Prompt, so a key
without it would hand Voice A's Prompt to Voice B.

Two things worth knowing:

**"Falls back to the default normalizer" is narrower than it sounds.** It is true
for a Text Format configured as `simple`: a Voice whose Language has no prompt
still gets the plain-text normalizer. It is not true for `openai`, where a
missing Prompt yields no normalizer and the request proceeds with its text as
written. That is not a failed request — the middleware treats no normalizer as
"nothing to do" — but it is not the `simple` normalizer either. Changing that
would alter what the server synthesizes for any deployment that opts into LLM
normalization without a Prompt per Language, so it is left as it is and pinned
by a test that says so.

**The shipped `type: simple` is left alone.** The shipped Prompt is reachable
once an operator opts into `openai`; flipping the shipped type would route every
Russian request through an LLM the shipped configuration does not have
credentials for.

`.env.example` needed no change: prompts are read only from the config file, and
a test now pins that the template carries no prompt key, so nobody adds one
believing the environment sets them.