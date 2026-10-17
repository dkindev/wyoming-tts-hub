---
title: "Fix the missing 'c' in the sentenizer spelling"
labels:
  - ready-for-human
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

- [x] No spelling of "sentenizer" remains in source, tests or docs
- [x] The abstract text-splitting type, its implementations, the factory, the
      modules and the operation are all renamed consistently
- [x] The glossary's **Sentence** term needs no change

## Answer

The family is now `Sentencizer`: the abstract type, its three implementations, the
factory, the three modules, the three test modules, the `sentencize*` operations,
and every log message and docstring beside them. One rule did it — `enteniz` →
`entenciz` — which is why the loguru placeholder keys moved in lockstep with the
log text that names them.

Two things were deliberately left alone:

- **`razdel`**, which spells its splitter `sentenize`. A blanket rename would have
  broken the import, so that one call site keeps the library's spelling.
- **Resolved tickets under `.scratch/`**, which record what was true when they were
  written.

Two docstrings said `SimpleTextSentencizer` and `RuSimpleTextSentencizer`, naming
types that do not exist — the types under test are the `PlainText` ones. The rename
would have carried that error forward, so the docstrings were corrected to name the
type they exercise. The test class names still say `Simple`; renaming those is a
separate concern from the spelling.

The local ruff is newer than the one the pre-commit hook pins, so running it across
the tree reformats unrelated files. Those reformats are not in this commit.

## Blocked by

None - can start immediately