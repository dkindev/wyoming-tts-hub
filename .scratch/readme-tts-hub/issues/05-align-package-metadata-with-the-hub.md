---
title: "Describe the package as the TTS Engine Hub it is"
labels:
  - ready-for-agent
created: 2026-10-18
---

## What to build

A client asking what this server is, and who to credit, is told it wraps the
Silero TTS engine and is credited to the distribution name — both left over from
before the hub existed, and both read straight out of the package metadata into
the Wyoming protocol's own program description.

Fix the metadata at its source so the protocol answer and every place the package
is described follow from it.

## Acceptance criteria

- [ ] The package summary describes a TTS Engine Hub aggregating TTS Engines,
      and no longer describes a server that wraps Silero
- [ ] The Wyoming program description a client receives is that summary
- [ ] The program's attribution names the project rather than the stale
      distribution name
- [ ] The repository's own description and keywords name the hub and the engine
      families it aggregates
- [ ] A test asserts the description served over the protocol is not the
      Silero-wrapping summary

## Blocked by

None (can start immediately).