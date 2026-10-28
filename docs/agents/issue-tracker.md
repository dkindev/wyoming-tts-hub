# Issue tracker: Local Markdown

Issues and specs for this repo live as markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket, numbered from `01`: `.scratch/<feature-slug>/NN-<slug>.md`
- Triage state is recorded in the `labels:` frontmatter array (role strings from `triage-labels.md`)

## Issue file shape

```yaml
---
title: "Issue title"
labels:
  - ready-for-agent
created: 2026-05-09
---

## What to build

...

## Acceptance criteria

- [ ] ...

## Blocked by

- NN-<slug>.md
```

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` (Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/NN-<slug>.md`, numbered from `01`, with the question in the body.
- **Blocking**: a `Blocked by:` section listing ticket numbers. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/` for tickets that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `labels: [claimed]` and save before any work.
- **Resolve**: append the answer under `## Answer`, record `resolved` in `labels`, then append a gist + link to the map's Decisions-so-far.
