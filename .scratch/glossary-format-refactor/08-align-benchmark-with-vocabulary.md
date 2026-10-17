---
title: "Align the benchmark script with current vocabulary and types"
labels:
  - ready-for-agent
created: 2026-10-17
---

## What to build

The benchmark script at the repo root still uses the retired pre-rename
vocabulary: "chunk" for what is now a **Sentence**, and a cache class that no
longer exists. It therefore does not run against the current server.

Bring it back to the current vocabulary — **Sentence**, **Chunk**, **Frame** —
and to the types that actually exist today.

## Acceptance criteria

- [ ] The benchmark imports no type that has been removed
- [ ] It uses **Sentence**, **Chunk** and **Frame** as the glossary defines them
- [ ] It runs end to end against the current server

## Blocked by

None - can start immediately