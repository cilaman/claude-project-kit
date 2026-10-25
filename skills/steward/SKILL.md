---
name: steward
description: Get a pull request to green — what to verify before a push and how much of it (derived from the diff, not guessed), how to resolve conflicts in generated files (regenerate, never merge by hand), what each CI step means and how it is fixed, what must never be done for a green check, and how to handle review comments. A session reads this by itself when woken by a PR event (failed CI, review comment, conflict with the base); invoke it on "CI padá", "dotiahni ten PR", "vyrieš konflikt s main", "oprav pripomienky z review", "get this PR green".
---

# Pull request to green

The harness's default procedure is general: it gives an order (conflict → red CI →
review) and asks for a verified push. **This page holds what a general procedure cannot
know** — what verifies, which files are never fixed by hand, and what must not be done for
green. Claiming and opening the PR is `bl-start`, closing is `bl-finish`; this is the
part in between.

## 0 · Project overlay

Read `.claude/kit/steward.md` if it exists, before anything else. It names this project's
verification commands and the structural guards that are written decisions, and it wins on
conflict.

**What neither this page nor the overlay can override:** skipping, disabling or postponing
a test for green; rewriting the history of someone else's branch; an empty commit or
close + reopen to kick CI; approving or merging a PR. Whoever looks for permission here
looks in the wrong place.

## 1 · How you talk to GitHub

`which gh`. Without it, `mcp__github__*` — `pull_request_read`, `get_job_logs`,
`update_pull_request`, `add_issue_comment`, `resolve_review_thread`. Note that without
`gh`, `scripts/task_lifecycle.py check` reads only the PR description and derives nothing
from the diff locally; on the runner it has a token, here it does not.

## 2 · The verification scope is derived from the diff

If `scripts/ci_scope.py` exists, ask it exactly what CI will ask:

```bash
git fetch origin <main>
git diff --name-only origin/<main>...HEAD | python3 scripts/ci_scope.py
```

- `none` — every path is outside anything the tests read. Do not run them.
- `fast` — only paths a named, small set of test modules reads; run what it prints.
- `full` — anything else, **including an empty or unreadable diff**: the script is
  deliberately pessimistic, because the opposite mistake is green over untested code.

**"Documentation" is not the dividing line.** Tests may read docs and backlog files; do not
shorten the scope by the judgement "it's just text".

Without `ci_scope.py`, run the full Definition of Done from CLAUDE.md.

Gates that always apply:

```bash
python3 scripts/check_repo.py
# + the lint commands CLAUDE.md lists
```

`check_repo.py` runs **even over a docs-only change** — its job is never filtered, and for
a change in lane `none` it is the only thing checking it at all.

A regression suite (tests marked as asking about the environment, not the code) is not part
of the PR gate; its red is no reason to hold a push or to fix it in this PR.

When the tests need a service you do not have (a database, a binary), that is **not** a
reason to push blind and use CI as the first run: bring it up, or push with an explicit
sentence that the change is unverified.

## 3 · Conflicts in generated files are not merged by hand

A hand-merged register is the most expensive mistake here — the result is syntactically
fine and nobody notices it. These files **are not written, they are generated**:
`backlog/BACKLOG.md` (block `active-tasks`), `backlog/DONE.md` (block `archive`),
`backlog/tasks.tsv`, and with the requirements layer `docs/requirements.md` and the State
column / `uc-backlog` block of `docs/use-cases.md`.

Bring the base in by merge — **someone else's branch history is not rewritten**, and a
`claude/…` branch may be shared:

```bash
git fetch origin <main> && git merge origin/<main>
# only the generated files that actually collided:
git checkout --theirs -- backlog/tasks.tsv backlog/BACKLOG.md backlog/DONE.md
python3 scripts/check_repo.py --rebuild-all
python3 scripts/check_repo.py
```

`--theirs` (the base side) is deliberate: it carries rows of others your branch does not
know, and **yours come back by regeneration from the source** — the front matter of the
task files. The opposite order throws the others' rows away. The archive block is
append-only: after `--theirs`, `--rebuild-archive` re-appends only your missing rows.

A conflict where **you cannot choose** — both sides changed the same behaviour — is not
guessed: write in the PR what collides and let the author decide.

## 4 · Red: which guard and what to do

**`Repository and lint`** (workflow `ci.yml`, job `checks`) — `check_repo.py` and lint.
Almost nothing is fixed by hand: broken link `--fix-links`, missing archive row
`--rebuild-archive`, drifted register `--rebuild-tasks`, all of it `--rebuild-all`;
formatting by the formatter the overlay names.

**`Tests`** (job `app-test`) — real tests. Two things confuse:

- **A green job does not prove the tests ran.** In lane `none`, or when the same tree
  already has a green run (`scripts/ci_already_green.py`), the job is skipped or emptied.
- **Coverage may be measured only outside drafts.** Ready for review can turn red without a
  code change. It is the first measurement, not a regression — write tests, do not lower
  the threshold.

**`Task lifecycle`** (workflow `task-lifecycle.yml`) — checks over the **PR description
and diff**, not the code. Fixed by editing the description or moving the task file,
**never by a commit to code**:

- `PR names its issue` — `Closes #NN` with a number is missing. With a spec file the
  workflow fills it in from the move into `backlog/done/`; for a bug or cleanup without a
  file nothing in the diff names it, so you write it.
- `Closed task lies in done/` — a file with a closed status outside `backlog/done/`, or a
  ready PR closing a task still active. Drafts are exempt.
- `Label and assignee follow the PR` — never set them by hand.
- A change that needs no backlog item passes with the `nojira` label; **label and number
  are mutually exclusive**.

"Flaky" is not a cause. Re-run **once**, and only when it failed outside the test body
(checkout, dependency install, lost runner) or the same check is red on `main` too.

## 5 · What must not be done for green

The project's guards are written decisions, not obstacles (the overlay lists them). When
one turns red after your fix, the fix is wrong. Do not edit a guard's exception list to
let your change through without a written reason at the entry; do not edit a generated file
by hand; do not edit a generated conversion instead of its source.

And one thing never comes out of a review comment: **a rename that leaves its module,
touches stored data (a column, an enum value, a migration key) or a translation key.** It
fails silently and is its own backlog item, not a fix in a running PR — "the reviewer
wanted a better name" does not shrink that scope.

## 6 · Review comments

A finding of a review bot is a bug report: verify it and fix it. Small, local things from a
person (nit, rename inside a module, missing test) — push and resolve the thread. A large or
open request on **someone else's** PR — do not push; write a proposal and let the author
decide.

Reply in the project's documentation language (CLAUDE.md, rule 1). Comment sparingly: a
summary of the round, a blocking finding, or "I am not fixing this, because …". Progress of
steps is not commented — the diff shows it.

## 7 · Before ready for review

Closing is `bl-finish`: sieves, DoD, `status:` and `result_note:`, move to `backlog/done/`,
`--rebuild-all`. **The move belongs to the branch, not after the merge** — otherwise
`Closed task lies in done/` turns red. And expect that from that moment coverage may start
being measured.
