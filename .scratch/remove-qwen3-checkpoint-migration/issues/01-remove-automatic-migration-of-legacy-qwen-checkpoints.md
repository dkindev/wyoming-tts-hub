# 01: Remove automatic migration of legacy Qwen checkpoints

**What to build:** Warming a Qwen3 engine downloads and reuses checkpoints only under `models/qwen3`; it no longer moves or deletes anything in a `models/qwen` directory. Operator documentation and tests describe only the `qwen3` layout.

**Blocked by:** None (can start immediately).

**Status:** completed

- [x] Checkpoints are downloaded to and loaded from `models/qwen3`, and no `models/qwen` directory is inspected, moved, or removed.
- [x] The migration helper, its legacy-directory constant, its lock, and the now-unused imports are gone.
- [x] The migration-only tests are removed, while the test asserting the `qwen3` download path remains.
- [x] The README still documents the `qwen3` checkpoint path but no longer claims automatic migration.
- [x] The test suite, ruff, and mypy pass.
