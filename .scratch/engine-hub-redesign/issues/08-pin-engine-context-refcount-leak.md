---
title: "Pin the Engine Context reference-count leak on cancellation"
labels:
  - ready-for-agent
created: 2026-10-05
---

Status: done

## Notes

Landed as `tests/test_engine_manager.py::TestCancelledAcquire::test_cancelled_acquire_leaves_the_model_evictable`,
which fails against current source with
`Deletion of model 'pinned' postponed: it is being used by 1 tasks`. The defect
and its likely fix are recorded in
[11-cancelled-acquire-pins-model-forever.md](11-cancelled-acquire-pins-model-forever.md).

## What to build

**This ticket lands a failing test.** It documents a defect rather than fixing
it. No production code changes here.

Acquiring an engine context increments the Model's reference count, then awaits
the per-Model concurrency semaphore, then marks the context as acquired. If the
caller is cancelled while that await is pending, the reference count was already
incremented but the release that runs on exit never happens.

The consequence is permanent: the Model appears to be in use forever, so eviction
defers indefinitely, the engine is never closed, and its memory — on a GPU, the
device memory too — is held for the life of the process. The only recovery is
restarting the server.

Write the test that pins the correct behaviour: a cancelled acquire must leave
the reference count as it was, so a subsequent eviction of that Model closes the
engine normally. The test should cancel a task blocked on the semaphore rather
than reaching into private state, and assert on the observable outcome (whether
the engine gets closed) rather than on the counter itself.

It will fail against current source. File the accompanying issue so a human can
decide whether to fix the acquisition path — most likely by releasing the
reference when the semaphore wait is cancelled, or by taking the reference only
after the wait succeeds.

## Acceptance criteria

- [x] A test cancels an acquire that is blocked on the per-Model concurrency
      limit and asserts the Model is still evictable afterwards
- [x] The test triggers cancellation through the public interface, without
      reaching into private task handles or counters
- [x] The test asserts on whether the engine is closed, not on an internal count
- [x] The test currently fails, and the failure demonstrates the leak rather than
      an unrelated error
- [x] No production code is changed by this ticket
- [x] An accompanying issue records the defect and the likely fix

## Blocked by

- [04: TTS Engine Manager owns Model loading, eviction, and shutdown](04-engine-manager-lifecycle.md)