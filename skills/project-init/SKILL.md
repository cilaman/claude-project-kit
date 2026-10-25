---
name: project-init
description: Initialise a repository with the project-kit method — CLAUDE.md with hard rules backed by guards, docs map and decision records, backlog where BL-NN is the GitHub issue number, claim protocol, generated indexes (BACKLOG.md, DONE.md, tasks.tsv), CI and task-lifecycle workflows, issue forms, labels, and optional layers (requirements RQ + use-case catalog UC, CI savings, Python/Django structural guards with tenant RLS). Interviews the user, renders the templates with scaffold.py, translates the prose into the project's documentation language, fills in the domain parts and verifies the result. Use for a new project or to adopt the method in an existing repo. Triggers: "inicializuj projekt", "založ nový projekt ako edilis", "nastav repo podľa project-kit", "bootstrap repo", "init project", "adopt the method here".
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
   use cases), `ci-savings` (test lanes from the diff, skip already-green trees, weekly
   regression — worth it once the suite takes minutes), `python-django` (structural
   guards; ask then about **tenancy**: multi-tenant data isolated by Postgres RLS).
4. **Commands** of the Definition of Done if not obvious: test command; for
   python-django the lint command, presentation module (`web`) and Django project package.

Do not ask what has a conventional default: `SRC_DIR=src`, `PYTHON_VERSION` from the
toolchain, `TODAY` from the date.

## 3 · Render

Write the variables to a JSON file in the scratchpad (every placeholder of CONVENTIONS.md
the chosen profiles use), then dry-run first:

```bash
python3 <skill-dir>/scaffold.py --out . --profiles requirements,ci-savings,python-django \
    --options tenancy --vars <scratchpad>/kit-vars.json --dry-run
```

Read the report: `skipped` are files that exist (decide per file: keep theirs and merge
ours in by hand, or `--force` when the existing one is a stub), `merge` are fragments
(`pyproject.fragment.toml` …) parked in `.kit-merge/`. Then run without `--dry-run`.

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
- With `python-django`: make sure `DOMAIN_MODULES` of `tests/structure/test_layering.py`
  will find the modules; with tenancy, adapt `TenantContextMiddleware` (URL shape,
  membership model) and the `APP_DB_ROLE` setting to the project.

## 6 · Verify

```bash
python3 scripts/check_repo.py --rebuild-all --no-issues
python3 scripts/check_repo.py --no-issues
python3 -m unittest discover -s tests/scripts -t .
```

`check_repo` also fails on any placeholder or condition marker left over. With
python-django, also the lint and test commands of the DoD (the structural guards need a
Django project to import; in an empty repo say so instead of skipping them silently).

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
what is not verified (e.g. the Django guards without a project), and the next step.
