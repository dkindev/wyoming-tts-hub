# 02: Make qwen3 the engine family

**What to build:** An operator can declare a model as `engine_type: qwen3`. The model is parsed, resolved to the Qwen3-TTS engine on the torch backend, and credited as `qwen3` to clients. The engine family member is named `QWEN3` and serializes as `qwen3`; the old `qwen` spelling is no longer accepted. Sample configuration, operator examples, and the domain glossary use the new name.

**Blocked by:** 01 - Simplify unsupported-checkpoint failures.

**Status:** completed

- [x] `EngineType` exposes `QWEN3` with the value `qwen3`; the old `QWEN` member is gone.
- [x] Configuration loading accepts `qwen3` and rejects `qwen` with an error naming the valid families.
- [x] The engine factory resolves a `qwen3` model to the Qwen3-TTS engine on the torch backend.
- [x] Voice attribution reports the engine family as `qwen3`.
- [x] Sample configuration, README examples, and the glossary use `qwen3` and `Qwen3-TTS`.
- [x] The test suite remains green.
