---
title: "Run the server from an installed console script"
labels:
  - ready-for-agent
created: 2026-10-18
---

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

- [ ] Installing the distribution provides a command that starts the server
- [ ] The command works from any working directory
- [ ] The command runs with no arguments using the shipped configuration
- [ ] The README's run instructions use the command rather than the module path
- [ ] The Docker image's default command is the same one
- [ ] A test starts the server through the command and asserts it comes up

## Blocked by

None (can start immediately).