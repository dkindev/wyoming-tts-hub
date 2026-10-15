---
title: "Reject audio that is not a sequence of samples"
labels:
  - ready-for-agent
created: 2026-10-15
---

## What to build

Audio with no sample axis is rejected where the audio is created, with a message naming the
problem, instead of failing later inside numpy at the Wyoming write.

A zero-dimensional audio array cannot be framed and cannot be announced to a client, and
nothing currently stops a TTS Engine producing one. Empty audio stays legal: an empty
payload is already skipped on the wire, which is the right behaviour for silence.

## Acceptance criteria

- [ ] Constructing a TtsResult with zero-dimensional audio raises, naming what is wrong with
      the audio
- [ ] Empty audio remains accepted
- [ ] A test covers the rejection, and existing audio tests are unchanged
- [ ] The rejection happens before any bytes are written to a client

## Blocked by

- None (can start immediately)