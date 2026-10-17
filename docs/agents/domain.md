# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Layout

**Single-context** — one `GLOSSARY.md` at the repo root, with ADRs in `docs/adr/`.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root, for the domain language: TTS Engine Hub, TTS Engine, Model Info, Active Model Info, Speaker, Voice, Language, Text Format, Sentence, Chunk, Frame, Text normalization, Prompt, SSML.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in.

If either doesn't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## Consumers

The following skills read these files:

- `improve-codebase-architecture` — reads `GLOSSARY.md` to learn the domain language, `docs/adr/` for architectural decisions
- `diagnosing-bugs` — reads `GLOSSARY.md` for context on the codebase
- `tdd` — reads `GLOSSARY.md` to understand domain concepts when naming tests
- `code-review` — checks that changes use the glossary's vocabulary
- `domain-modeling` — maintains `GLOSSARY.md` and writes ADRs
- `grill-with-docs` — maintains `GLOSSARY.md` and writes ADRs as decisions get resolved

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids — e.g. say **TTS Engine Hub**, not "server" or "orchestrator".

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0003 (per-model speaker cache), but worth reopening because…_
