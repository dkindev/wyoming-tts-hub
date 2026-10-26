# 03: Rename the Qwen3 implementation and checkpoint directory

**What to build:** The Qwen3-TTS engine's class, module, and test module carry the Qwen3 name. Checkpoints are fetched and reused under the `qwen3` directory inside the Models directory, and any checkpoints already downloaded under the old `qwen` directory are moved across rather than fetched again. Operator documentation points at the new directory.

**Blocked by:** 01 - Simplify unsupported-checkpoint failures; 02 - Make qwen3 the engine family.

**Status:** completed

- [x] The engine class, its module, and its test module are named for Qwen3.
- [x] Imports and test patch targets follow the renamed module.
- [x] Checkpoints are downloaded to and reused from the `qwen3` directory inside the Models directory.
- [x] Existing checkpoints under the old `qwen` directory are moved to the new directory.
- [x] Operator documentation references the new checkpoint directory.
- [x] No stale `qwen_engine` or `QwenTtsEngine` references remain; the external `qwen_tts` package is untouched.
- [x] The test suite remains green.
