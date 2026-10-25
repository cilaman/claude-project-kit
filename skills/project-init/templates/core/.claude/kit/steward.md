# Overlay — steward (PR to green) for {{PROJECT_NAME}}

Extends `project-kit:steward`; wins on conflict. See [README.md](README.md).

## Verification commands

Always, also for a documentation-only change:

```bash
python3 scripts/check_repo.py
# kit:if python-django
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

Lane `none` — do not run tests; `fast` — run exactly the arguments the script prints;
`full` — the whole suite. The lists behind the lanes live in `scripts/ci_scope.py` and
are kept honest by `tests/scripts/test_ci_scope.py`.
<!-- kit:endif -->

## Guards that are written decisions

When one of these turns red after a fix, the fix is wrong, not the guard.

<!-- kit:if python-django -->
- `tests/structure/test_layering.py` — domain modules do not import or name
  `{{PRESENTATION_MODULE}}/` (imports, route names, template tag libraries).
- `tests/structure/test_writes.py` — `{{PRESENTATION_MODULE}}/` does not write to the
  database; the domain service writes. An exception only by name in `ALLOWED_WRITES`,
  with its reason.
- `tests/structure/test_language_policy.py` — code, file names and identifiers in
  English (CLAUDE.md, rule 1).
- `tests/structure/test_skips.py` — every place a test can skip is declared with who
  answers the question instead.
<!-- kit:endif -->
<!-- kit:if tenancy -->
- `tests/tenancy/test_rls_policies.py` — a tenant model has its row-level-security
  policy, and a model linked to the organization that is deliberately not tenant data is
  named with its reason in `NON_TENANT_WITH_ORGANIZATION`. **Silence is not a decision.**
<!-- kit:endif -->
- Generated blocks (`<!-- generated: … -->`) and `backlog/tasks.tsv` are never edited by
  hand — `python3 scripts/check_repo.py --rebuild-all`.

## Lessons of this project

<!-- One rule per entry, with one sentence about the incident that taught it.
     Workflow only — domain invariants become guards. -->
