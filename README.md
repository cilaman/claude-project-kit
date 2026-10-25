# project-kit

A Claude Code plugin that sets up — and then runs — a repository organisation method for
work shared by people and parallel Claude sessions: **backlog item = GitHub issue,
claim = pushed branch, generated indexes, one fact = one home, hard rules backed by
guards.** Why each rule exists: [METHOD.md](METHOD.md).

## What is inside

| Piece | What it does |
|---|---|
| skill `project-init` | interviews you, renders the templates into a repo (`scaffold.py`), translates the prose, fills in the domain parts, verifies |
| skill `bl-start` | issue → claim commit → draft PR with `Closes #NN` |
| skill `bl-finish` | sieves (screenshots, adversarial review, mutation), DoD, close the item, regenerate, decide what stays |
| skill `bl-bug` | triage a bug report into issue(s): verdict, duplicates, cause, permalinks |
| skill `steward` | get a PR green: scope of verification, generated-file conflicts, what each CI step means |
| skill `decision-record` | write or amend a decision record in `docs/decisions/` |
| skill `guard` | turn a prose invariant into a test with anti-vacuum, reverse direction and mutation proof |
| hook `guard_generated.py` | refuses hand edits of generated blocks and `backlog/tasks.tsv` |
| templates | profiles `core`, `requirements`, `ci-savings`, `python-django` (+ `tenancy`) — see [CONVENTIONS.md](skills/project-init/CONVENTIONS.md) |

The scripts the templates install (`check_repo.py`, `task_lifecycle.py`,
`github_labels.py`, `ci_scope.py`, `ci_already_green.py`) are standard-library Python and
belong to the new repo afterwards — they evolve there with the project.

## Install

```text
/plugin marketplace add ~/Private/Projects/claude-project-kit
/plugin install project-kit@project-kit
```

(or push this repo somewhere and add it by git URL). Restart the session; the skills
appear as `project-kit:project-init`, `project-kit:bl-start`, …

## Use

In the new (or existing) repository:

```text
/project-kit:project-init
```

or just say "inicializuj projekt podľa project-kit". Without the plugin, paste
[INIT-PROMPT.md](INIT-PROMPT.md) into a session.

Project-specific lessons about the workflow go to `.claude/kit/<skill>.md` in the
project — every plugin skill reads its overlay first.

## Developing the kit

```bash
python3 -m unittest discover -s tests -t .   # renders every profile combination and checks it
```

A change to a name (marker, flag, key, step) starts in CONVENTIONS.md.
