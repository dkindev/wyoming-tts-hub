---
title: "Rename the glossary term to Model Info"
labels:
  - ready-for-agent
created: 2026-10-17
---

## What to build

The domain language names the entity the way the code does. The glossary's term becomes **Model
Info** (and **Active Model** becomes **Active Model Info**), every reference to it in the
relationships and the example dialogue follows, and the flagged ambiguity about "model" is
re-worded to record that the qualified name is now carried by the entity itself rather than only
by convention. The docs that list the glossary's terms are updated to match.

The glossary's lower-case prose about a "named, language-specific model" is left as it is: the
underlying thing is still a model, and **Model Info** is what this codebase calls the record of it.
The term's "avoid" list stays, and is now enforced by the name.

## Acceptance criteria

- [x] The glossary's term is **Model Info**, with **Active Model Info** for the allowlisted subset
- [x] Every reference to the term in the definitions, relationships and example dialogue uses the
      new name
- [x] The flagged ambiguity about "model" records that the qualified name is carried by the entity
      itself
- [x] The term list in the agent domain docs names **Model Info** and **Active Model Info**
- [x] Terms unrelated to this rename are untouched
- [x] Lower-case prose that means the underlying model, and any operator-facing wording the glossary
      quotes, is unchanged

## Blocked by

- 08 - Delete the old Model names