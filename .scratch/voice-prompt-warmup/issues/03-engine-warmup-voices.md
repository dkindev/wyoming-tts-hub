# 03: Engine protocol: `warmup(voices)` + lazy single-voice warm

**What to build:** Every TTS Engine accepts an optional list of Voices along with a warm-up call. When a synthesis request hits a cold engine, the engine warms the model and pre-builds the Voice Prompt for the requested voice — so the first sentence of a session no longer pays the Voice Prompt build latency. Engines without Reference Audio (Silero, OpenAI-compatible) ignore the voices entirely.

**Blocked by:**
- 02-derive-voice-warmup.md

**Status:** ready-for-agent

- [x] The engine warm-up protocol accepts Voices, defaulting to none, threading through to the model-loading layer
- [x] A cold engine reached via synthesis warms the model plus the requested voice's Voice Prompt
- [x] The Qwen3 engine builds Voice Prompts for supplied voices, bounded by the prompt-cache capacity
- [x] Prompt-cache capacity comes from the `max_voice_prompts` setting (equal to default 8 when unset)
- [x] Silero and OpenAI engines accept the new signature and ignore Voices
- [x] Warm-up stays idempotent; the per-request Voice Prompt cache path is unchanged
- [x] Qwen3 tests cover: single-voice lazy warm, flagged voice list bounded by capacity, a failed build skipped with a warning
