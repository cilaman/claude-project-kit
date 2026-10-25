---
id: BL-XX
title: Short name of the task
priority: P2            # P1–P3
status: NEW             # NEW / IN_PROGRESS / NEEDS_INPUT / BLOCKED / DONE / OBSOLETE
created: YYYY-MM-DD
# kit:if requirements
parent: —               # business requirement RQ-NN above the task, or — (em dash)
# kit:endif
depends_on: —           # BL-AA, BL-BB ascending, or — (em dash); see the comment below
source: where the task came from (session, decision record, incident, issue)
# kit:if requirements
uc: —                   # UC-XX, UC-YY ascending, or —; the key stands last
# kit:endif
---

<!-- `depends_on:` carries a **hard dependency** — "this task cannot start before that
     one is done", because it lacks a schema, a component, a decision or a tool. The
     generated index orders by it, so a task never stands above what it stands on.
     Thematic kinship or "nice to do together" does **not** belong here. A finished
     dependency is not listed; a missing id or a cycle is an error.
     `status_note: >` (folded) is an optional sentence about where the task stands, shown
     in the generated index; `result_note: >` replaces it when the task closes — the
     sentence about what came **out** of it, from which the archive row is written. -->
<!-- kit:if requirements -->
<!-- `uc:` names the use cases whose behaviour the task delivers — the one home of that
     link; the catalog's State column is derived from it. A task that only enables a
     case (spike, analysis, tooling) or is cross-cutting has `uc: —` and says the link
     in prose under Goal. **An item born from a defect claims no use case**: it restores
     behaviour the catalog already counts as delivered. `parent:` is the requirement the
     task works off — membership has its one home here. -->
<!-- kit:endif -->

## Context

Why the task exists.

## Goal

Measurable outcome.

## Steps

- [ ] step 1

## Definition of Done

- [ ] `python3 scripts/check_repo.py` green
- [ ] `{{TEST_COMMAND}}` green
- [ ] <task-specific gates>

## ⚠️ Risks and open questions

- …
