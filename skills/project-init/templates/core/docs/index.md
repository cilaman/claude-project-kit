# Documentation map

> **Status:** live · {{TODAY}}
> **Parent:** [../CLAUDE.md](../CLAUDE.md)
> **Origin:** initialisation from project-kit
> **Scope:** the entry point routing to every document of `docs/`; does NOT hold any fact of its own

Every document of `docs/` has a row here — `scripts/check_repo.py` fails on one that
does not. A new document gets its row in the same commit that creates it.

## Method

| Document | What you find there |
|---|---|
| [documentation-principles.md](documentation-principles.md) | the four principles, header block, decision records, comments |
| [architecture.md](architecture.md) | modules, layers, boundaries, open questions |
<!-- kit:if requirements -->
| [requirements.md](requirements.md) | business requirements `RQ-NN`, their acceptance and generated state |
| [use-cases.md](use-cases.md) | catalog of use cases `UC-NN` with a generated State column |
<!-- kit:endif -->

## Decisions

| Document | What you find there |
|---|---|
| [decisions/task-tracking.md](decisions/task-tracking.md) | backlog ↔ GitHub issues, claim protocol, generated indexes, ceremony |
