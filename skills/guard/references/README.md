# Worked examples of stack-native guards

Each directory is **one stack's** implementation of guards whose shape is universal. They
are reference material for the skill `guard`, not templates: nothing here is copied into
a project by `project-init`. Read them for the shape — anti-vacuum, the reverse
direction, exceptions named with a reason, asking the database catalog instead of the
framework — and write the guard in the project's own stack.

| Directory | Stack | What it shows |
|---|---|---|
| `python-django/` | Python, Django, PostgreSQL | layering over the AST, no ORM writes in the presentation, a skip inventory, ASCII identifiers, row-level-security policies checked in `pg_policies` with a reverse guard over every model linked to the organization; `pyproject-excerpt.toml` and `.pre-commit-config.yaml` pin the linter to the lock file |

The examples use the concrete names of a sample project (`web`, `myproject`, `src/`).
