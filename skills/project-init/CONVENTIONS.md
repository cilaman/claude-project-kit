# Kit conventions — the contract every template, script and skill shares

This page is the one home of every name the kit's pieces must agree on. A script, a
template and a skill that spell a marker, a flag or a key differently fail silently —
the generated block is never found, the step reads as green. Change a name here first,
then everywhere it is used.

## Profiles and template layout

`skills/project-init/templates/<profile>/<path in the new repo>`

| Profile | Always? | Carries |
|---|---|---|
| `core` | yes | CLAUDE.md, README, docs map + principles + decision records (`docs/decisions/task-tracking.md` = the method itself, `_TEMPLATE.md`), backlog, GitHub forms/labels/PR template, CI + task-lifecycle + (optional) regression workflows, the `setup-toolchain` action, `check_repo.py`, `task_lifecycle.py`, `github_labels.py`, their tests, `.claude/kit/` overlays |
| `requirements` | optional | `docs/requirements.md` + `docs/requirements/_TEMPLATE.md` (RQ layer), `docs/use-cases.md` (UC catalog) |
| `ci-savings` | optional | `ci_scope.py`, `ci_already_green.py`, their tests, `ci.yml` variant with lanes |
| `architecture` | optional | `architecture.toml` + `check_architecture.py` (any language: layers via imports, forbidden constructs with named exceptions, declared skips, ASCII file names) and its tests |

**No profile is tied to a stack.** The only fixed technology is the process scripts'
Python 3.11+ (standard library) and GitHub (issues, Actions). Everything about the
project's own stack is in three places: the commands below, the `setup-toolchain`
action, and stack-native guards written by the skill `guard` (worked examples in
`skills/guard/references/`).

Profiles apply in the order of the table; a later profile's file at the same path
**replaces** the earlier one. A file named `*.fragment.<ext>` is **merged** into
`*.<ext>` (or becomes it when the target does not exist) instead of being copied.

## Placeholders

`{{NAME}}` — replaced at init, never left in the new repo (`check_repo.py` fails on one).
An optional placeholder may be the empty string; templates use it only inside a
`var:NAME` condition.

| Placeholder | Meaning | Example |
|---|---|---|
| `{{PROJECT_NAME}}` | display name | `Edilis` |
| `{{PROJECT_SLUG}}` | repo/package-safe name | `edilis` |
| `{{PROJECT_DESCRIPTION}}` | one paragraph: what the product is, for whom | |
| `{{GITHUB_REPO}}` | `owner/name` | `cilaman/edilis` |
| `{{MAIN_BRANCH}}` | default branch | `main` |
| `{{DOC_LANGUAGE}}` | language of docs, backlog, issues, PRs | `Czech` |
| `{{TODAY}}` | init date, `YYYY-MM-DD` | |
| `{{SRC_DIR}}` | source root | `src` |
| `{{TOOLCHAIN}}` | preset of `setup-toolchain`: `none`, `python`, `node`, `java`, `dotnet`, `go`, `rust`, `other` (fails loudly until written by hand) | `node` |
| `{{SETUP_COMMAND}}` | optional: installs dependencies after the toolchain | `npm ci`, `uv sync --frozen` |
| `{{TEST_COMMAND}}` | test command of the DoD | `npm test`, `./gradlew test`, `go test ./...` |
| `{{LINT_COMMAND}}` | optional: lint command(s) of the DoD | `npm run lint`, `uv run ruff check .` |
| `{{REGRESSION_COMMAND}}` | optional: the suite that asks about the environment; empty = no regression workflow | `npm run test:regression` |

## Conditional blocks

Kept or dropped at init depending on the chosen profiles; the markers themselves are
always removed.

- Markdown / HTML: `<!-- kit:if <profile> -->` … `<!-- kit:endif -->`
- YAML / Python / TOML / shell: `# kit:if <profile>` … `# kit:endif`

`<condition>` is a profile name (`requirements`), a non-empty variable
(`var:LINT_COMMAND`) or a variable with a value (`TOOLCHAIN=node`), optionally negated
with `!` (`# kit:if !architecture`). No nesting. A file whose **first line**
carries `kit:file <condition>` (inside any comment syntax) is dropped whole when the
condition is off; the marker line is removed when it is on. `scaffold.py` applies all of
this — it is the only implementation.

## Backlog

- Item id `BL-NN` **is the GitHub issue number**. No zero padding.
- Spec file (optional): `backlog/BL-NN-kebab-slug.md`, ASCII, lower-case.
  Closed (DONE, OBSOLETE) files live in `backlog/done/` and only there.
- Statuses: `NEW`, `IN_PROGRESS`, `NEEDS_INPUT`, `BLOCKED`, `DONE`, `OBSOLETE`.
- Priorities: `P1`, `P2`, `P3`.
- Empty value: `—` (em dash, U+2014).
- Front-matter keys, **fixed order** (absent optional keys are skipped, order of the
  rest holds): `id`, `title`, `priority`, `status`, `created`, `parent`, `depends_on`,
  `source`, `status_note`, `result_note`, `uc`.
  - Required always: `id`, `title`, `priority`, `status`, `created`, `source`.
  - Required on an active task: `depends_on`.
  - Required when the `requirements` profile is on: `parent`, `uc`.
  - `status_note:` / `result_note:` are folded scalars (`>` + indented lines).
  - Inline comments `  # …` after a value are allowed (the template carries them).
- Requirement: `docs/requirements/RQ-NN-kebab-slug.md`, numbered by hand from `RQ-01`.
- Use case: row `| UC-NN | … |` in `docs/use-cases.md`, numbered by hand from `UC-01`.
- Ids `BL-`, `RQ-`, `UC-` are never renamed or reused; replacement = new record
  linking the old one.

## Generated blocks

Opening marker `<!-- generated: <name> -->`, closing marker `<!-- /generated -->`.
Nothing between them is typed by hand; the hook `hooks/guard_generated.py` refuses an
Edit/Write that changes it and `check_repo.py` fails CI when it drifts.

| Name | File | Written by flag |
|---|---|---|
| `active-tasks` | `backlog/BACKLOG.md` | `--rebuild-backlog` |
| `archive` | `backlog/DONE.md` | `--rebuild-archive` (append-only) |
| `requirements` | `docs/requirements.md` | `--rebuild-requirements` |
| `uc-backlog` | `docs/use-cases.md` | `--rebuild-uc` |

Fully generated files (no markers, never edited): `backlog/tasks.tsv`
(`--rebuild-tasks`). The **State** column of the UC catalog tables is generated too
(`--rebuild-uc`), cell by cell.

`check_repo.py` flags: `--fix-links`, `--rebuild-backlog`, `--rebuild-tasks`,
`--rebuild-archive`, `--rebuild-requirements`, `--rebuild-uc`, and `--rebuild-all`
(= `--fix-links` + every rebuild the enabled layers have). Exit 0 = OK, 1 = violations.

`backlog/tasks.tsv` columns: `id priority status parent depends_on uc path title`.

## GitHub

- Labels (`.github/labels.yml`, complete — a label not in the file is deleted):
  `bug`, `chore`, `needs-spec`, `in-progress`, `nojira`, `escaped-dod`, and when `{{REGRESSION_COMMAND}}` is given
  also `regression`.
- Branch: `bl-<NN>-<slug>`; claim commit (may be empty):
  `chore(backlog): claim — <title> — BL-NN`.
- PR description first line: `Closes #NN` (with the number). `nojira` label and a
  number are mutually exclusive.
- Workflow `ci.yml`: job `checks` named **`Repository and lint`**, job `app-test` named
  **`Tests`** (`ci_already_green.py` looks the latter up by this display name).
- Workflow `task-lifecycle.yml`: job named **`Task lifecycle`**; steps
  **`PR names its issue`** (`task_lifecycle.py check`), **`Closed task lies in done/`**
  (`finished`), **`Label and assignee follow the PR`** (`sync`).
- Commit: `type(scope): description — BL-NN`; types `feat`, `fix`, `test`, `docs`,
  `chore`, `refactor`, `ci`; `docs(backlog)` / `docs(decisions)` for those areas; a new
  guard is `test(<scope>): guard — <invariant> — BL-NN`.
- The main branch is written once, in CLAUDE.md (`Main branch: \`main\``, section
  Structure). Plugin skills are not rendered, so they read it from there.

## Tests

- Kit scripts' tests are `unittest` (stdlib), runnable as
  `python3 -m unittest discover -s tests/scripts -t .` in projects without pytest.
- The regression suite (asks about the environment, not the code) is whatever
  `{{REGRESSION_COMMAND}}` runs; it is outside the Definition of Done and runs in
  `regression.yml`, which exists only when the command is given.

## Project overlays of plugin skills

`.claude/kit/<skill>.md` in the project repo extends the plugin skill of that name
(`bl-start`, `bl-finish`, `bl-bug`, `steward`, `decision-record`, `guard`). Every plugin
skill reads its overlay **first** when it exists; on conflict the overlay wins. Lessons
learned about the *workflow* of one project land in its overlay, not in the plugin.
`.claude/kit/README.md` explains this inside the project.

## Language

Kit itself (skills, scripts, templates): English. Code of the new repo: English.
Docs, backlog, issues, PRs, commit descriptions: `{{DOC_LANGUAGE}}` — init translates
the prose of the templates; it never translates keys, statuses, markers, flags, label
names, file names or placeholders.
