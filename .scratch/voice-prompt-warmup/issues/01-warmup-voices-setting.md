# 01: Setting surface: `warmup_voices` + `max_voice_prompts`

**What to build:** Operators can configure both settings anywhere `warmup_models` works — YAML, repeated CLI flags, env — with the same validation story: a null list coerces to an empty list, and the prompt-cache cap validates like the model-cache cap. Setting them has no runtime effect yet; this ticket is the config surface only.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [x] `warmup_voices` parses from a shipped-style YAML list, repeated CLI flags, and env
- [x] A null/absent `warmup_voices` coerces to `[]`
- [x] `max_voice_prompts` parses with a default equivalent to the current hard-coded prompt-cache capacity, and rejects invalid values like the model-cache cap does
- [x] `config.yml` documents both settings with CLI/env comments
- [x] Config parsing tests pass for both settings
