---
title: "Fix the missing 'c' in the sentenizer spelling"
labels:
  - ready-for-agent
created: 2026-10-17
---

## What to build

The text-splitting family that produces **Sentences** is spelled "sentenizer"
everywhere — the abstract type, its implementations, the factory and the module
names. The glossary's term is **Sentence**, so the code contradicts the domain
language in every reference to it.

This is a mechanical rename across a small surface: no behaviour changes, so it
needs no expand–contract sequence — but do it in one commit, since splitting the
rename from the test updates leaves the suite red.

## Acceptance criteria

- [ ] No spelling of "sentenizer" remains in source, tests or docs
- [ ] The abstract text-splitting type, its implementations, the factory, the
      modules and the operation are all renamed consistently
- [ ] The glossary's **Sentence** term needs no change

## Blocked by

None - can start immediately