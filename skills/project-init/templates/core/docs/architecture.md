# Architecture

> **Status:** live · {{TODAY}}
> **Parent:** [index.md](index.md)
> **Origin:** initialisation from project-kit
> **Scope:** modules of `{{SRC_DIR}}/` and their responsibility, layers and dependency direction, conventions of the code, open questions of architecture; does NOT describe the process (CLAUDE.md, [decisions/task-tracking.md](decisions/task-tracking.md))

## Modules

| Module | Responsibility (one sentence) | Depends on |
|---|---|---|
| *(first module)* | | |

## Layers and direction of dependencies

<!-- kit:if python-django -->
`{{PRESENTATION_MODULE}}` is the only module that knows HTTP and HTML; it calls domain
modules, never the other way round (CLAUDE.md rule 6). The database is written by a
domain service, not by a view (rule 7) — so a second caller (an API, a command, a job)
gets the same write, the same checks and the same audit trail.
<!-- kit:endif -->
<!-- kit:if tenancy -->
Tenant isolation is a property of the database: row-level security on every tenant
table, the context set by `core.tenancy` only (rule 9). Without a context a tenant
table returns nothing — failing into emptiness, not into somebody else's data.
<!-- kit:endif -->
*(Describe the layers as they appear.)*

## Conventions

*(Naming, ids, time zones, money, … — one home per convention.)*

## Open questions

Every item is either struck through (answered, with a link) or names the active backlog
item that owns it.

1. *(none yet)*
