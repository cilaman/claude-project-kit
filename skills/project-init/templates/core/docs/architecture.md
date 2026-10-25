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

<!-- kit:if architecture -->
The layers and what each may use are declared in [../architecture.toml](../architecture.toml)
— that file is their one home and `scripts/check_architecture.py` enforces it
(CLAUDE.md rules 6–8). This section says **why** the layers are cut where they are.
<!-- kit:endif -->
*(Describe the layers as they appear.)*

## Conventions

*(Naming, ids, time zones, money, … — one home per convention.)*

## Open questions

Every item is either struck through (answered, with a link) or names the active backlog
item that owns it.

1. *(none yet)*
