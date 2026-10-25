# Catalog of use cases (UC)

> **Status:** live · {{TODAY}}
> **Parent:** [index.md](index.md)
> **Origin:** initialisation from project-kit
> **Scope:** the complete list of use cases with actor, wave and note; the **State** column and the table "Link to the backlog" are generated from the backlog and never edited by hand; does NOT describe screens or entities

## How to use the catalog

- **A UC id is never changed or reused.** A cancelled case stays in the table with the
  wave `cancelled`; a replaced one links its successor.
- **Wave** is the order of introduction, not a promise: **V0** foundations, **V1** the
  first delivered value, **V2** the next pillar, **V3** extensions. It also answers
  "what is in scope now" — no separate MVP decision is needed.
- **State is not typed.** It is derived from the `uc:` key of backlog items (OBSOLETE
  ones ignored): **delivered** = claiming items exist and all are DONE; **in progress**
  = at least one moved and not all are DONE; **not started** = none, or only NEW. The
  wave `cancelled` overrides everything. Rewrite with
  `python3 scripts/check_repo.py --rebuild-uc`.
- **A defect claims no use case** (`uc: —`): it restores behaviour already counted as
  delivered and would push the case back to *in progress*.

## A — <First area>

| ID | Use case | Actor | Wave | State | Note |
|---|---|---|---|---|---|
| UC-01 | <Actor does something to get some value> | <Actor> | V0 | not started | |

## Link to the backlog

<!-- generated: uc-backlog -->
<!-- /generated -->
