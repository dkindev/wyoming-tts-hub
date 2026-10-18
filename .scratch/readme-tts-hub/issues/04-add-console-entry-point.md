---
title: "Run the server from an installed console script"
labels:
  - ready-for-agent
created: 2026-10-18
---

Status: done

## What to build

Running the server requires knowing that the package's entry point is invoked
as a module inside a source directory, which is not something a reader can guess
from an installed package, and which breaks the moment the working directory
changes.

The distribution installs no command. The only way in is invoking a module inside
the source tree, and the package's own metadata lookup requires the
distribution to be installed — so "install it" and "run it" are entangled in a
way the reader has to discover by hitting the error.

Give the distribution a command that starts the server, and document that command
as the way to run it.

## Acceptance criteria

- [x] Installing the distribution provides a command that starts the server
- [x] The command works from any working directory
- [x] The command runs with no arguments using the shipped configuration
- [x] The README's run instructions use the command rather than the module path
- [x] The Docker image's default command is the same one
- [x] A test starts the server through the command and asserts it comes up

## Blocked by

None (can start immediately).
## Answer

The distribution installs `silero-server`, pointing at a `run()` that wraps
`asyncio.run(main())` and swallows the interrupt — the `python -m src.main` block now
calls it too, so the two ways in cannot drift. The image's `CMD` and the README both
use the command, and the README now says plainly that the command runs from anywhere
while the configuration it reads is found relative to the working directory.

**The distribution was uninstallable as it stood, which this ticket exposed.** The
packaging named only the top package, so a wheel held `src/main.py` and none of the
code it imports: `src.tts` and `src.tts.preprocessing` were absent, and the installed
command — or any plain `pip install .` of the server — failed on import. Verified by
building the wheel both ways. Packaging now discovers every subpackage under `src`, and
a test compares what setuptools would find under `src` against what the distribution
declares, so narrowing it again fails rather than shipping an unimportable wheel.

Each criterion is pinned, and each pin was checked against the state it guards:

- The command is read out of the *installed* metadata rather than trusted from
  `pyproject.toml`, since until the distribution is reinstalled nothing is on the path.
- Run bare, with no arguments and no environment, from a directory holding a
  configuration — the reader who typed the command.
- It answers a real `describe` over a socket and is asserted to offer the Voice the
  data file declares, rather than merely binding a port that any listener could satisfy.
- Ctrl-C is sent as a signal, not raised as an exception: the server installs its own
  handler and cancels the running task, so an injected `KeyboardInterrupt` would prove
  nothing about the path a real interrupt takes. It exits 0 with no traceback.
- The image's default command, and the wheel's contents, are both asserted.

Nothing here reaches the network: the Model Infos the tests boot carry no `warmup`, and
the Engine Manager warms up only those that do.

The command is named for the distribution as it stands, `silero-server`. The sibling
rename ticket owns moving both to the hub's name; that is where this one changes again.
