# 04: Manager startup: pass flagged voices

**What to build:** At server startup, engines warming on behalf of flagged voices build those voices' Voice Prompts up front, so the first request for any warmed voice is cheap. Each voice is warmed up to prompt-cache capacity; a voice whose prompt build fails is warned and skipped without stopping startup. Warm-up still runs concurrently with server startup.

**Blocked by:**
- 03-engine-warmup-voices.md

**Status:** ready-for-agent

- [ ] The Engine Hub passes warm-up-flagged voices (per model, sliced to prompt-cache capacity) into each engine's warm-up call
- [ ] Warm-up flagged voices only for the engine's own model
- [ ] A failing voice prompt build logs a warning and the remaining voices still warm; the engine still starts (mirrors the model warm-up skip tests)
- [ ] Engines already loaded are not re-warmed (idempotence preserved)
- [ ] Engine-manager tests verify voices are forwarded to the warm-up call
