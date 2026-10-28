---
title: "Add EngineType and language capabilities to the Model"
labels:
  - ready-for-agent
created: 2026-08-13
---

## What to build

Extend the **Model** configuration concept so it carries the capabilities the
**TTS Engine Hub** will later use for language selection and text-format
gating. Today a Model is `{id, enabled, warmup, hash_prefix}`; extend it to the
resolved schema below. The schema came out of a domain-design grilling session
and is the decision to implement:

```python
class EngineType(Enum):
    SILERO = "silero"
    QWEN = "qwen"
    OPENAI = "openai"

@dataclass(frozen=True)
class Model:
    id: str
    engine_type: EngineType                    # required, no default
    ssml_supported: bool = False
    language_auto_detected: bool = False
    languages: list[str] = field(default_factory=list)  # frozen -> default_factory
    enabled: bool = True
    warmup: bool = False
    hash_prefix: str | None = None
```

Update the shared test model factory so existing no-arg call sites keep
compiling unchanged (the engine test file must not need touching). Rewrite the
stale Model unit tests, which reference the already-deleted `language` field,
and add coverage for the new fields, their defaults, `EngineType`, and the
frozen dataclass. Also repair the stale Voice (`locale`) and `TTSResult`
(bytes → `np.ndarray`) model test cases so the model test file is green.

## Acceptance criteria

- [x] `EngineType` enum exists with `SILERO`, `QWEN`, `OPENAI` values
- [x] `Model` gains required `engine_type` and defaulted `ssml_supported`, `language_auto_detected`, `languages` (frozen, `default_factory` for `languages`)
- [x] Existing `Model(...)` constructions across the test suite keep working via the updated shared factory (defaults preserve no-arg call sites)
- [x] Model unit tests cover new fields, defaults, `EngineType`, and frozen-dataclass behavior
- [x] `tests/test_tts_models.py` is green (stale `language`/`locale`/bytes-`TTSResult` assertions removed)

## Blocked by

None — can start immediately
