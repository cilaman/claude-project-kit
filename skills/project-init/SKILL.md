---
name: project-init
description: Initialise a repository with the project-kit method — CLAUDE.md with hard rules backed by guards, docs map and decision records, backlog where BL-NN is the GitHub issue number, claim protocol, generated indexes (BACKLOG.md, DONE.md, tasks.tsv), CI and task-lifecycle workflows, issue forms, labels, and optional layers (requirements RQ + use-case catalog UC, CI savings, language-agnostic architecture guards). Works for any stack — the stack enters only through the DoD commands, the CI toolchain action and the stack-native guards it writes for the project's non-negotiable invariants. Interviews the user, renders the templates with scaffold.py, translates the prose into the project's documentation language, fills in the domain parts and verifies the result. Use for a new project or to adopt the method in an existing repo. Triggers: "inicializuj projekt", "založ nový projekt ako edilis", "nastav repo podľa project-kit", "bootstrap repo", "init project", "adopt the method here".
---

# Initialising a repository with project-kit

The method itself is [METHOD.md](../../METHOD.md); the names every piece shares are
[CONVENTIONS.md](CONVENTIONS.md). This page is the order of work. `scaffold.py` and
`templates/` lie next to it — use the base directory of this skill to call them.

The mechanical half (copying, conditions, placeholders) is the script's; **the half that
needs judgement is yours**: what the project is, which rules it needs, the translation,
the first modules and use cases. Do not hand-copy templates — a hand copy drops a
condition marker or a placeholder, and nothing tells you.

## 1 · Look before asking

In the target directory (usually the working directory):

```bash
git rev-parse --show-toplevel 2>/dev/null; git remote get-url origin 2>/dev/null
git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || git branch --show-current
ls -a; which gh && gh auth status; python3 --version
```

From that derive what you can: GitHub repo, main branch, stack (`pyproject.toml`,
`manage.py`, `package.json`), existing `CLAUDE.md`/`README.md`/`docs/`/`backlog/`. **An
existing repo is an adoption, not a fresh start** — note what already exists, because
scaffold never overwrites without `--force` and you will merge by hand. With issues or PRs
already on GitHub, the first free number is above them: set `SERIES_FIRST_NUMBER` in
`scripts/check_repo.py` to the next number (`gh api repos/<owner>/<repo>/issues?state=all&per_page=1 --jq '.[0].number'`).

## 2 · Interview — only what you could not derive

One `AskUserQuestion` round, recommended option first:

1. **Name and one paragraph** — what the product is, for whom (→ `PROJECT_NAME`,
   `PROJECT_SLUG`, `PROJECT_DESCRIPTION`).
2. **Documentation language** — of docs, backlog, issues, PRs (code is always English).
3. **Layers** (multi-select): `requirements` (RQ + UC catalog — products with a client and
   use cases), `ci-savings` (test lanes from the diff, skip already-green trees — worth it
   once the suite takes minutes), `architecture` (layer boundaries, forbidden constructs,
   declared skips, for any language — recommend it whenever there is or will be code).
4. **Stack**, when the repo does not show it: the toolchain preset (`python`, `node`,
   `java`, `dotnet`, `go`, `rust`, `none`, or `other` — then you write the
   `setup-toolchain` steps yourself) and the commands: dependencies (`SETUP_COMMAND`),
   tests, lint (optional), regression suite (optional).
5. **Non-negotiable invariants of the domain** — "what must never happen, whatever the
   code looks like?" (data of one customer visible to another, money as a float, a write
   bypassing the audit trail, …). Each answer becomes a hard rule with a guard in step 5.

Do not ask what has a conventional default: `SRC_DIR=src`, `TODAY` from the date, the
toolchain and commands when the repo already shows them (`package.json` scripts,
`pyproject.toml`, `build.gradle`, `go.mod`, `Cargo.toml`, `*.csproj`).

## 3 · Render

Write the variables to a JSON file in the scratchpad (every placeholder of CONVENTIONS.md
the chosen profiles use), then dry-run first:

```bash
python3 <skill-dir>/scaffold.py --out . --profiles requirements,ci-savings,architecture \
    --vars <scratchpad>/kit-vars.json --dry-run
```

Read the report: `skipped` are files that exist (decide per file: keep theirs and merge
ours in by hand, or `--force` when the existing one is a stub), `merge` are fragments
parked in `.kit-merge/`. Then run without `--dry-run`.

Merge every `.kit-merge/` file into its target by hand — keep the project's existing
values, add ours — and **delete `.kit-merge/`**. A missing value fails loudly: scaffold
refuses a file with an unknown placeholder.

## 4 · Translate the prose (when the language is not English)

Translate into the documentation language: `CLAUDE.md`, `README.md`, `docs/**/*.md`,
`backlog/*.md`, `.github/ISSUE_TEMPLATE/*.yml` (labels, descriptions), the PR template,
the `description:` values in `.github/labels.yml`, `.claude/kit/*.md`, and the `LABELS`
dict in `scripts/check_repo.py` (the words the generated tables print — the State words
there are what the catalog is compared against, so the catalog uses the same words).

**Never translate:** front-matter keys, statuses (`NEW`, `DONE` …), priorities, generated
markers, script flags, label names, workflow job and step names, file names, ids, code.
Keep the meaning sharp rather than literal; these documents are rules, and a softened
rule is a different rule.

## 5 · Fill in the domain parts

- `CLAUDE.md`: the module list under Structure as far as it is known; drop or add hard
  rules so that **every rule names its guard or says out loud that nobody guards it**. A
  rule without either is an aspiration — prefer writing the guard (skill `guard`).
- `docs/architecture.md`: the first modules and their direction of dependencies.
- With `requirements`: replace the placeholder area and `UC-01` row of
  `docs/use-cases.md` with the real first area — or leave one honest row; never invent a
  catalog the user has not described.
- With `architecture`: fill `architecture.toml` — `languages`, the layers as they exist
  (or as decided, with `empty = "why"` until code lands), the first `[[forbidden]]`
  rules that follow from the hard rules. Run
  `python3 scripts/check_architecture.py --list-files` and check every source file lands
  in the layer you meant.
- `.github/actions/setup-toolchain/action.yml`: check the preset's versions against the
  repo (`.nvmrc`, `go.mod`, `global.json`, …); with `TOOLCHAIN=other` write the steps.
- **Every invariant from the interview** becomes a numbered hard rule in CLAUDE.md with
  its guard — a `[[forbidden]]` rule when words suffice, otherwise a stack-native test
  written with the skill `guard` (its `references/` show the shapes, e.g. tenant
  isolation checked in the database catalog). An invariant that cannot be guarded yet
  is written with "nobody guards this yet — BL-NN" and gets its issue.

## 6 · Verify

```bash
python3 scripts/check_repo.py --rebuild-all --no-issues
python3 scripts/check_repo.py --no-issues
python3 -m unittest discover -s tests/scripts -t .
```

`check_repo` also fails on any placeholder or condition marker left over. Then
`python3 scripts/check_architecture.py` (with that layer) and the project's own lint
and test commands — in an empty repo some cannot run yet; say so instead of skipping
them silently.

## 7 · GitHub — outward-facing, confirm first

Each of these changes shared state; ask before running them:

- `python3 scripts/github_labels.py --dry-run`, then without it — **the label file is
  complete**: GitHub's default labels are deleted, which also strips them off existing
  issues. In an adopted repo with labelled issues say that explicitly.
- The first commit: `chore: initialise project organisation (project-kit)`. In an empty
  repository it goes straight to the main branch (there is no CI to gate a PR yet); in an
  adopted one it is a branch and a PR labelled `nojira` — or the first `BL-NN` issue if
  the adoption needs decisions.
- The first real task follows the protocol: skill `bl-start`.

## 8 · Report

Say what was rendered, what was merged by hand, what you chose for the user (defaults),
what is not verified (e.g. CI before the first push, a guard without code to walk yet),
and the next step.
