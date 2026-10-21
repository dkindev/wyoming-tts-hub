---
title: "Pin a Model Info to an upstream model revision"
labels:
  - completed
created: 2026-10-19
---

## What to build

Operators need to reproduce exactly which upstream checkpoint a Model Info
serves. Upstream model repositories are mutable; a restart can otherwise load
different weights than the ones that were tested.

Add an optional revision to the Model Info, read from the data file. A Model Info
that names a revision is fetched at that immutable commit; one that omits it
follows upstream. Treat an absent value and an empty value the same way, as the
data file already does for other optional fields.

Do not fold this into the existing checksum pin. That field verifies the bytes of
a downloaded file locally; a revision asks upstream for a named commit. They are
different guarantees and must stay separately readable in the data file.

## Acceptance criteria

- [x] Model Info carries an optional revision
- [x] The data file parser reads revision, treating absent and empty as unset
- [x] Model Infos that declare no revision behave exactly as before
- [x] The existing checksum pin is unchanged in both behaviour and meaning
- [x] Tests cover a declared revision, an absent revision, and an empty revision

## Blocked by

None — can start immediately
