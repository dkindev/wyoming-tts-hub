# 05: Operator docs (+ glossary term)

**What to build:** Operators can discover and use the feature from shipped docs: the README and config.yml explain `warmup_voices` and `max_voice_prompts` with working examples. The glossary records the settled term so future sessions use the same language.

**Blocked by:**
- 04-manager-startup-voices.md

**Status:** ready-for-agent

- [x] README documents both settings, their defaults, id format, and the cap behaviour
- [x] config.yml comments match the README language
- [x] GLOSSARY.md gains a Voice Prompt warm-up entry consistent with existing Reference Audio / Voice Prompt entries, without implementation detail
- [x] No ADR (per decision in planning)
- [x] README example tests still pass
