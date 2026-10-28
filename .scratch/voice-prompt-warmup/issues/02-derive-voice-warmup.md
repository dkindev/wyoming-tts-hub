# 02: Derive `Voice.warmup` in data storage

**What to build:** At startup the data storage marks each Voice as warm-up-selected using the configured ids, with the same operator ergonomics as model warm-up: an unknown warm-up voice id fails startup naming every offender; an id whose model isn't served is warned about and skipped; a warm-up flag written in the voice data file stays inert (config owns it). Each Voice carries a boolean showing whether it was selected.

**Blocked by:**
- 01-warmup-voices-setting.md

**Status:** ready-for-agent

- [x] Voice ids `"{model id}-{voice name}"` from the config become a derived warm-up flag on each Voice
- [x] Unflagged Voices default to not maximally warmed (flag False)
- [x] Unknown warm-up voice id(s) fail startup naming every offending id
- [x] A warm-up id on a Voice whose Model Info isn't active warns and is skipped
- [x] A warm-up flag written in the voice data file is inert (config list does not get overridden by it)
- [x] The warm-up list is inert when a supplied configuration is used, matching model-warm-up behaviour
- [x] Voice and model tests cover the default flag value and derivation
