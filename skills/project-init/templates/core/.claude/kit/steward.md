# Overlay — steward (PR to green) for {{PROJECT_NAME}}

Extends `project-kit:steward`; wins on conflict. See [README.md](README.md).

## Verification commands

Always, also for a documentation-only change:

```bash
python3 scripts/check_repo.py
# kit:if architecture
python3 scripts/check_architecture.py
# kit:endif
# kit:if var:LINT_COMMAND
{{LINT_COMMAND}}
# kit:endif
```

Tests:

```bash
{{TEST_COMMAND}}
```

<!-- kit:if ci-savings -->
The scope of the tests is derived from the diff, the same way CI derives it:

```bash
git fetch origin {{MAIN_BRANCH}}
git diff --name-only origin/{{MAIN_BRANCH}}...HEAD | python3 scripts/ci_scope.py
```

Lane `none` — do not run tests; `fast` — only the process-script tests
(`python3 -m unittest discover -s tests/scripts -t .`); `full` — the whole suite. The lists behind the lanes live in `scripts/ci_scope.py` and
are kept honest by `tests/scripts/test_ci_scope.py`.
<!-- kit:endif -->

## Guards that are written decisions

When one of these turns red after a fix, the fix is wrong, not the guard.

<!-- kit:if architecture -->
- `scripts/check_architecture.py` over `architecture.toml` — layer boundaries, forbidden
  constructs and declared skips. An exception is added only by name, **with its reason**;
  widening a layer's `may_use` to make a red import green is a design decision, not a fix.
<!-- kit:endif -->
- *(Native guards of this stack, as they are written — one line each: path, what it
  holds.)*
- Generated blocks (`<!-- generated: … -->`) and `backlog/tasks.tsv` are never edited by
  hand — `python3 scripts/check_repo.py --rebuild-all`.

## Lessons of this project

<!-- One rule per entry, with one sentence about the incident that taught it.
     Workflow only — domain invariants become guards. -->
