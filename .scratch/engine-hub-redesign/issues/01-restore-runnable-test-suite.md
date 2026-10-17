---
title: "Restore a runnable test suite"
labels:
  - ready-for-agent
created: 2026-10-05
---

Status: ready-for-agent

## What to build

The test suite currently executes zero tests. The Engine Hub redesign deleted
several types from the domain models and removed the exceptions module, but the
shared test fixtures were never updated. Collection aborts on the fixture module
before any test runs, so every test file is dark.

Restore a suite that collects and runs. This is the prefactor for all remaining
Engine Hub coverage work.

Concretely:

- Drop the fixtures whose subject types no longer exist: the ones that build a
  runtime configuration object, the ones that build a per-request normalization
  options object, and the package-importer patch that targeted the old
  single-module engine (that patching now belongs to the Silero engine module).
- Keep and re-point the fixtures that remain meaningful: the OpenAI-compatible
  client double, the data storage double, and the default normalization settings.
- Retarget the shared test helpers at the new architecture. The helper that
  collects synthesized sentences calls the Engine Hub's entry point, not a TTS
  Engine's, so its name should say so. The Voice and Model builders still match
  the domain types and should stay, gaining passthrough for declared languages,
  SSML support, and warmup.
- Delete the three test files that test deleted API surface outright: the
  monolithic engine test file, the text normalizer test file, and the
  OpenAI normalizer test file. Their still-valid intent is carried forward by
  later tickets; the rest is genuinely obsolete.

## Acceptance criteria

- [x] `pytest tests` collects without an import error and executes tests
- [x] No test file or fixture imports a name that no longer exists in the domain
      models, and nothing imports the removed exceptions module
- [x] The previously-obsolete test files are gone from the tree
- [x] The suites that were already green (cache, data storage, sentence
      splitting, sentence splitting factory, normalizer factory, voice
      normalization end-to-end) still pass
- [x] No test reaches into private state of a class under test to arrange a
      scenario

## Blocked by

None — can start immediately.