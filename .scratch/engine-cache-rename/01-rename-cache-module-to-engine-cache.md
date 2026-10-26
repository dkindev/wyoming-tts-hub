---
title: "Rename cache module to engine_cache"
labels:
  - ready-for-agent
created: 2026-10-26
---

## What to build

The in-memory cache of loaded **TTS Engines** lives in a module named for what it actually
caches. Every production and test importer resolves through `engine_cache` instead of the
generic `cache` module name, and the matching test module is renamed to follow it. The class
keeps its name, `ExponentialDecayCache`; this ticket is a module rename, not a class or API
rename. The old module is gone with no compatibility shim, and historical `.scratch/` records
keep their original references.

## Acceptance criteria

- [ ] `src/tts/engine_cache.py` exists and `src/tts/cache.py` is gone, with history preserved by a
  rename rather than a delete-and-add
- [ ] All live production and test imports of the old module path point at `engine_cache`
- [ ] The cache test module is renamed to match, and its tests still pass
- [ ] `ExponentialDecayCache` keeps its name and behaviour unchanged
- [ ] No compatibility module or re-export shim is added
- [ ] Historical files under `.scratch/` are left untouched
- [ ] `ruff check src tests` and `pytest tests/` pass

## Blocked by

None - can start immediately.
