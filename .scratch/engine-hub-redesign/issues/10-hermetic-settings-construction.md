---
title: "Settings construction is hermetic"
labels:
  - ready-for-agent
created: 2026-10-05
---

Status: done

## What to build

Server settings are assembled from several sources at once: command-line
arguments, process environment variables, a gitignored local environment file,
and the repository's checked-in config file. When no config path is given, the
YAML source silently falls back to the config file in the working directory.

That makes the config tests depend on the machine they run on. Three assertions
in the Active Model tests fail on a configured workstation — one sets an Active
Models allowlist in its local environment file, which outranks the fixture
config the test wrote — while passing in CI, where none of that is present. The
suite is green or red depending on who ran it.

Make settings construction hermetic so a test sees only what it set up. Two
leaks to close:

- Process environment variables prefixed for the server must not reach a test
  that did not set them.
- The gitignored local environment file must not be read at all during tests.
- The YAML source must resolve to a per-test config path rather than the
  repository's checked-in one.

Verified by: the Active Model tests pass unchanged while the environment carries
an allowlist that would otherwise override them, and pass again when that value
is removed.

This is deliberately separate from restoring collection — it is a correctness
property of the suite, not a precondition for running it.

## Acceptance criteria

- [x] Every test starts with server-prefixed environment variables cleared,
      except the ones the test itself sets
- [x] The local environment file is not read during tests
- [x] The YAML config source resolves to a per-test path, never the repository's
      checked-in config file
- [x] The three Active Model config tests pass with a conflicting allowlist
      present in the environment
- [x] Config tests that assert on other settings — device, backend type, Models
      directory, URI — still pass
- [x] A test can still override a setting through the environment when it means
      to

## Blocked by

- [01: Restore a runnable test suite](01-restore-runnable-test-suite.md)