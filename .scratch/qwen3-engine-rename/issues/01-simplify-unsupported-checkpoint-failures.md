# 01: Simplify unsupported-checkpoint failures

**What to build:** When a Qwen3-TTS checkpoint declares a family the engine cannot synthesize with, warmup still refuses it before loading, now with a plain runtime error instead of an engine-specific exception type. The Qwen engine uses the shared warmup path, and the detailed family message remains available as the wrapped cause. Remove the custom exception and the Qwen-specific warmup override.

**Blocked by:** None (can start immediately).

**Status:** completed

- [x] Unsupported checkpoint families are rejected before the checkpoint is loaded.
- [x] Both checkpoint-rejection paths raise a plain runtime error.
- [x] The custom exception type and the Qwen-specific warmup override are gone.
- [x] The rejection test verifies the detailed family message through the wrapped cause.
- [x] The test suite remains green.
