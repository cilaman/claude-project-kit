# CLAUDE.md — rules for the `{{PROJECT_SLUG}}` repository

{{PROJECT_DESCRIPTION}}

The repository is organised by the method in
[docs/decisions/task-tracking.md](docs/decisions/task-tracking.md): a backlog item is a
GitHub issue, a spec file exists only when a design is needed, a task is claimed by
pushing a branch, and everything that can be computed (indexes, registers, states) is
generated, never typed. The entry point to the documentation is
[docs/index.md](docs/index.md).

## Hard rules

1. **Language policy.** Documentation, backlog, issues, pull requests and the
   descriptions of commits are written in {{DOC_LANGUAGE}}. **Source code is English
   throughout** — identifiers, file names, commands, tests, comments, docstrings and the
   database schema.
<!-- kit:if python-django -->
   That every identifier and Python file name is ASCII is guarded by
   `tests/structure/test_language_policy.py`; **the human language of identifiers,
   comments and documentation is guarded by nobody** and stays with review.
<!-- kit:endif -->
<!-- kit:if !python-django -->
   **Nobody guards the language** of identifiers, comments and documentation; it stays
   with review.
<!-- kit:endif -->
2. **One fact = one home.** Every fact has exactly one authoritative document; the
   others link to it. The method is
   [docs/documentation-principles.md](docs/documentation-principles.md). A document
   without a header block, or one the map does not route to, fails
   `scripts/check_repo.py`.
3. **Backlog conventions.** A backlog item is `BL-NN`, and that number **is the number
   of the GitHub issue**; **the spec file is optional.** `backlog/BL-NN-kebab-slug.md`
   is written only when a design is needed: when the **solution is being decided**
   (several ways at different cost), when it reaches into several modules, or when it
   has its own Definition of Done beyond "tests green". Everything else — a bug, a
   cleanup — stays an issue. The front-matter keys, their **fixed order** and meaning
   live in [backlog/_TEMPLATE.md](backlog/_TEMPLATE.md).
<!-- kit:if requirements -->
   `uc:` is the only home of the link task → use case and `parent:` the only home of
   the link task → requirement; **an item born from a defect claims no use case**
   (`uc: —`) — a machine cannot enforce that, it stays with review.
<!-- kit:endif -->
   **Generated files are never edited by hand** — CI fails and the next rebuild throws
   the edit away: the active section of [BACKLOG.md](backlog/BACKLOG.md), the archive
   [DONE.md](backlog/DONE.md) and the register [tasks.tsv](backlog/tasks.tsv)
<!-- kit:if requirements -->
   (and with them the overview in [docs/requirements.md](docs/requirements.md) and the
   State column of [docs/use-cases.md](docs/use-cases.md))
<!-- kit:endif -->
   are written by `python3 scripts/check_repo.py --rebuild-all`.
   **For "what is BL-NN" do not open a document — grep `backlog/tasks.tsv`.**
<!-- kit:if requirements -->
4. **Immutable identifiers.** `BL-NN`, `RQ-NN` and `UC-NN` are never changed or
   reused; a replacement is a new record linking the old one.
<!-- kit:endif -->
<!-- kit:if !requirements -->
4. **Immutable identifiers.** `BL-NN` is never changed or reused; a replacement is a
   new record linking the old one.
<!-- kit:endif -->
5. **A claim is a pushed branch, not a promise.** The order holds **even for a one-line
   fix**: (1) open the issue — the server assigns the number and it is the `BL-NN`;
   (2) **push the branch `bl-NN-slug` with its own claim commit** (an empty one is
   enough) — if the push fails, somebody has the task; **a bare branch holds no
   claim**; (3) **a draft PR at once**, with **`Closes #NN` and the number** in its
   description; (4) the `in-progress` label and the assignee are **never set by hand** —
   the workflow derives them from the PR; (5) the merge closes the issue through that
   line. **Moving the spec file to `done/` belongs to the branch, before ready for
   review.** A claimed task is not taken over. Whoever abandons a claim clears it. A
   trifle that needs no backlog item at all passes with the `nojira` label on the PR —
   it holds no claim, and label and number exclude each other.
   **The protocol is run by the skills `bl-start` and `bl-finish`** — invoke them,
   do not retype it from memory. Why it is a push and who owns what:
   [docs/decisions/task-tracking.md](docs/decisions/task-tracking.md).
<!-- kit:if python-django -->
6. **The domain does not know HTTP.** `{{SRC_DIR}}/{{PRESENTATION_MODULE}}/` may call
   domain modules; a domain module must not import `{{PRESENTATION_MODULE}}`, name its
   routes (`"{{PRESENTATION_MODULE}}:…"`) or `{% load %}` its tag libraries. Guarded by
   `tests/structure/test_layering.py`.
7. **The database is written by a domain service.** `{{PRESENTATION_MODULE}}/`
   validates a form and hands over `cleaned_data`; `Model.save()`, `ModelForm.save()`,
   `objects.create/update/delete` or `bulk_create` must not appear there. An exception
   exists only by name in `ALLOWED_WRITES`, with its reason. Guarded by
   `tests/structure/test_writes.py`.
8. **Every skipped test is a decision.** A `skip`, `skipif` or `importorskip` is
   declared in `DECLARED_SKIPS` with who answers the question instead. Guarded by
   `tests/structure/test_skips.py`.
<!-- kit:endif -->
<!-- kit:if tenancy -->
9. **Tenant isolation belongs to the database.** A tenant entity inherits from
   `core.models.TenantModel` and its migration carries `core.db.rls_operations(<table>)`;
   the context is set **only** through `core.tenancy` (middleware, or the context
   manager outside a request), never by a hand-written `SET`. A model linked to the
   organization that deliberately is not tenant data is named, with its reason, in
   `NON_TENANT_WITH_ORGANIZATION` — silence is not a decision. Guarded by
   `tests/tenancy/test_rls_policies.py`.
<!-- kit:endif -->

## Structure

Main branch: `{{MAIN_BRANCH}}`

```
{{PROJECT_SLUG}}/
├── CLAUDE.md            # this file — rules, structure, Definition of Done
├── README.md            # what it is, how to run it
├── backlog/             # spec files of backlog items; generated BACKLOG.md, DONE.md,
│                        # tasks.tsv; closed items in done/
├── docs/                # documentation; entry point index.md, decisions in decisions/
├── scripts/             # process scripts (check_repo.py, task_lifecycle.py, github_labels.py)
├── {{SRC_DIR}}/                 # source code — modules described in docs/architecture.md
├── tests/               # tests; they also guard the hard rules
├── .claude/kit/         # project overlays of the project-kit skills
└── .github/             # CI, task lifecycle, issue forms, labels, PR template
```

Modules of `{{SRC_DIR}}/` (one sentence each; the authoritative description is
[docs/architecture.md](docs/architecture.md)): *(fill in as modules appear)*.

## Definition of Done

- `python3 scripts/check_repo.py` green.
<!-- kit:if python-django -->
- `{{LINT_COMMAND}}` and `{{TEST_COMMAND}}` green. **The regression suite is not part
  of it** — tests marked `regression` ask about the environment, not the code, and run
  in the weekly workflow.
<!-- kit:endif -->
<!-- kit:if !python-django -->
- `{{TEST_COMMAND}}` green, and `python3 -m unittest discover -s tests/scripts -t .`
  for the process scripts.
<!-- kit:endif -->
- Backlog updated: `status:` and `result_note:` in the front matter, the file moved to
  `done/`, then `python3 scripts/check_repo.py --rebuild-all` (archive row, active
  section, register — all generated). New documents are linked from
  [docs/index.md](docs/index.md). The skill `bl-finish` runs this.
- Commit messages reference the backlog item (`— BL-NN`); types per
  [docs/decisions/task-tracking.md](docs/decisions/task-tracking.md#commits).
