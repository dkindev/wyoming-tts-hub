---
title: "Onion middleware chain can post-process audio"
labels:
  - ready-for-agent
created: 2026-10-30
---

# 01: Onion middleware chain can post-process audio

**What to build:** A synthesis request runs through one ordered onion chain where
every middleware can act before synthesis and/or transform the audio stream after
it. Pre-processing still resolves the Language, splits Sentences, and applies Text
Normalization exactly as today. The terminal step validates the request and
acquires the engine only after every middleware's pre-processing has run. A
middleware can freely transform, drop, or pass through the audio it receives
after synthesis.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] A middleware can transform the audio stream after synthesis and its output
      is what the Hub yields
- [x] Pre-processing middleware run in list order and post-processing runs in
      reverse list order
- [x] Language resolution, Sentence splitting, and Text Normalization behave as
      before and their existing tests pass unchanged in intent
- [x] An invalid Language or Text Format is still rejected after pre-processing
      and before any engine is acquired
- [x] Closing the Hub's audio stream early cancels and closes the upstream
      synthesis stream
- [x] Framing is still performed by the Hub; this ticket changes only the
      middleware chain shape
