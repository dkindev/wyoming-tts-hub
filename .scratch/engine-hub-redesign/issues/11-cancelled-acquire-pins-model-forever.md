---
title: "A cancelled Engine Context acquire pins the Model forever"
labels:
  - ready-for-agent
created: 2026-10-06
---

Status: done

## Notes

The reference is now given back when the wait is cancelled, rather than taking it
after the wait:

```python
self._acquire_engine_ref(self._model_id)

try:
    await self._cached_engine.semaphore.acquire()
except asyncio.CancelledError:
    self._release_engine_ref(self._model_id, self._cached_engine)
    raise
```

The first suggested fix — taking the reference only once the wait has succeeded
— does fix the leak but introduces a second defect, which
`TestQueuedAcquire::test_queued_acquire_defers_eviction_of_the_model` pins: a
request already queued on the per-Model limit holds no reference, so eviction is
not deferred for it and the cleaner tears the Model down underneath the waiter.
The waiter then wakes to `AttributeError: 'CachedTtsEngine' object has no
attribute 'engine'` (`src/tts/engine_manager.py:67`), having lost both the engine
and the semaphore it was blocked on. The window in which the reference is held
during the wait is load-bearing, not incidental — it is what keeps a queued
waiter alive.

Both defects are pinned by independent tests: the leak by
`TestCancelledAcquire::test_cancelled_acquire_leaves_the_model_evictable`, the
queued-waiter regression by the test above. Each fails against the other's
implementation.

## The defect

`TtsEngineContext.__aenter__` (`src/tts/engine_manager.py:61`) takes the Model's
reference **before** awaiting the per-Model concurrency semaphore:

```python
async def __aenter__(self):
    self._acquire_engine_ref(self._model_id)

    await self._cached_engine.semaphore.acquire()
    self._acquired = True
```

The release lives in `__aexit__` (`src/tts/engine_manager.py:70`), which only runs
when the `async with` body is entered. A caller cancelled while the semaphore wait
is still pending never enters the body, so `__aexit__` never runs and the
reference is never given back.

The reference count is then permanently one too high. When the cache evicts that
Model, `_handle_cache_eviction` sees it as in use and moves it to
`_pending_eviction`; the background cleaner only drains `_dead_pool`, so the
eviction is deferred indefinitely. The engine is never closed, and its memory —
on a GPU, the device memory too — is held for the life of the process. The only
recovery is restarting the TTS Engine Hub.

## How it shows up

Any client that gives up while waiting its turn: a Home Assistant client that
cancels a request when another TTS request starts, a client whose timeout fires
behind a slow sentence, or a shutdown of an upstream pipeline mid-queue. The
TTS Engine Hub keeps serving, so nothing looks broken — it just quietly stops
being able to evict that Model.

## Reproduction

`tests/test_engine_manager.py::TestCancelledAcquire::test_cancelled_acquire_leaves_the_model_evictable`
pins the correct behaviour and fails against current source, logging:

```
WARNING | _handle_cache_eviction: Deletion of model 'evictable' postponed: it is being used by 1 tasks.
```

The count never returns to zero, so the engine is never closed.

## Likely fix (superseded — see Notes)

Take the reference only once the wait has succeeded, so a cancelled acquire never
holds one:

```python
async def __aenter__(self):
    await self._cached_engine.semaphore.acquire()
    self._acquire_engine_ref(self._model_id)
    self._acquired = True
```

This change fixes the leak and passes every test in the suite at the time it was
written, which is why it was originally preferred: the deferral coverage of
`test_model_in_use_is_closed_only_after_its_request_completes` only exercises a
request that *holds* the Model, never one *queued* on the limit, so it does not
cover the case this breaks. The alternative — releasing the reference when the
wait is cancelled — keeps the window where the reference is held during the
wait. That window is exactly what eviction deferral relies on for a request that
has begun acquiring, so the smaller change is not safe here. Notes records what
was actually landed and the test that pins the difference.

## Acceptance criteria

- [x] `test_cancelled_acquire_leaves_the_model_evictable` passes
- [x] A cancelled acquire leaves the Model's reference count unchanged
- [x] Eviction of a Model with a cancelled acquire still closes its engine once
- [x] Deferral for a Model genuinely in use still works
- [x] Deferral for a request already queued on the per-Model limit still works

## Blocked by

- [08: Pin the Engine Context reference-count leak on cancellation](08-pin-engine-context-refcount-leak.md)