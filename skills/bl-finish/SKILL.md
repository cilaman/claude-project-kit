---
name: bl-finish
description: Close a backlog item — run the sieves green tests cannot replace (screenshots, targeted adversarial review, mutation of your own new tests) BEFORE saying done, walk the Definition of Done, write `status:` and `result_note:`, move the spec file to `backlog/done/`, let `check_repo.py --rebuild-all` write archive, index and register, verify the PR carries `Closes #NN`, and finally decide what of the session's findings stays permanently (guard > docstring > memory > overlay; default "nothing"). Use when work on BL-NN is finished, before ready for review. Triggers: "dokonči úlohu", "uzavri BL-…", "hotovo, zavri to", "ready for review", "finish the task", "close BL-…".
---

# Closing a backlog item

The end of a task has more steps than it seems, and the forgotten ones are silent —
nobody notices them until a month later, when nobody can tell what was finished.

## 0 · Project overlay

Read `.claude/kit/bl-finish.md` if it exists, before anything else. It extends this page
for this project and wins on conflict (extra gates, screenshot viewports, review
dimensions).

## 1 · The sieves — and green tests are the weakest of them

**This step comes first, not last.** The opposite order once let a branch pass the whole
DoD — every test, lint and `check_repo` — while carrying several real defects, two of them
crashes reachable from every screen. The automatic sieves caught none of them.

| Sieve | Catches | When |
|---|---|---|
| DoD (tests, lint, `check_repo`) | invariants someone already wrote as a guard | always |
| **Screenshots before and after** | geometry nothing measures | every change touching a screen; include the small laptop viewport the overlay names |
| **Adversarial review** | invariants that exist in the repo only as **prose** | when a trigger from `bl-start` §7 holds |
| **Mutation of your own new tests** | a guard that checks vocabulary instead of behaviour | every test written in this run |

"Done" is not said before every applicable sieve has run and its findings are fixed.
Ready for review is switched only then.

**Mutate your own new tests.** The guard you just wrote is the only one in the repo nobody
knows protects anything — history proved the others. Especially a **textual** guard over
JS, CSS or a document: it checks words, not behaviour, and a guard can pass over the very
defect it was written for because the word it looks for survived one line lower in an
assignment. The procedure is mechanical: change one expression in the source, run that one
test, **see it fail**, revert, check `git diff`. Pin the **effect**, not a decision about it.

**A test you rewrote counts as new.** When a changed boundary breaks an old test and you
move it so it passes again, it may have stopped guarding what it was born for — e.g. moved
to a date where another condition already decides the outcome. Mutate the condition the
test names in its title.

Two traps in the test itself: an assert over a **set**, or over two copies of the same
input, cannot fail on order (two equal sets iterate equally — check order over a **list**
deliberately given in the wrong order); and a field that carries a verdict must be tested
in a state where it is the **only** thing flipping the verdict, otherwise something beside
it holds the result and the mutation passes.

**Running the adversarial review:** several reviewers by dimension (correctness, data
isolation/security, browser, conventions, fulfilment of the requirement) and an
**adversarial verifier over every finding** — a reviewer tasked to refute a finding drops
most false ones. Findings are **verified by reproduction**, not copied from the report.

A defect found **after** a green DoD gets an issue with the label `escaped-dod` and one
line in the body: "Sieve that should have caught it: …". Over time that query says where
to invest.

**Reviewers write into the working tree, and `git add -A` commits it.** A reproduction is a
probe test file the reviewer usually deletes — not always, not immediately, and in
parallel with you. Before committing during a review run `git status --short`, or name the
files (`git add <path>`). If reviewers run the test suite against a shared resource (a test
database, a port), give each its own, and run the full suite only after the review ends.

## 2 · Definition of Done

From CLAUDE.md, plus the task's own gates when it has a spec file. Typically:

```bash
python3 scripts/check_repo.py
# + the lint and test commands CLAUDE.md lists
```

## 3 · Backlog — two things by hand, the rest by the script

Only for an item **with a spec file**; an issue-only item has no step here.

By hand, both in the front matter of the task file:

1. `status: DONE` (`OBSOLETE` when it will not be done — the file is never deleted; the
   reason why not is part of the history),
2. `result_note: >` — **one sentence about the outcome**, author's prose: not what was
   done, but what came of it. `status_note:` is removed at closing — "where it stands"
   says nothing about a finished task.

Move the file into `backlog/done/` (a closed status anywhere else is an error) and leave
the rest to the tool:

```bash
python3 scripts/check_repo.py --rebuild-all
python3 scripts/check_repo.py
```

`--rebuild-all` repairs links the move made one directory deeper, appends the archive row
to `backlog/DONE.md` from `result_note:`, regenerates the active index, the register
`backlog/tasks.tsv`, and — when the requirements layer exists — the requirement overview
and the use-case State column. **Do not open the archive or the index to do it by hand:**
that is the whole reason a script writes them — reading a large index to add one line is
the cost the split exists to avoid. Do not pipe the check into `tail`; a hidden red line
is still red.

Register new documents in `docs/index.md`.

**Do this before switching the PR to ready for review** — the step
**`Closed task lies in done/`** checks it and is silent on drafts. A move missed before
merge lets `Closes #NN` close the issue of a task that is still active, and `main` drifts.

## 4 · The PR description carries the number

```bash
gh pr view --json body -q .body | grep -iE 'closes #[0-9]+'
```

(without `gh`: `mcp__github__pull_request_read`). The merge closes the issue. **Do not
close it another way** — not by a CI step, not by hand; two paths to one write are two
places to drift. A missing number is fixed by editing the description; the guard also runs
on `edited`, no push needed.

## 5 · Commits

Every substantive commit ends with `— BL-NN`, also for an item without a spec file;
commit types per CLAUDE.md.

## 6 · What you do not clean up by hand

The `in-progress` label and the assignee come off via `task-lifecycle.yml` when the PR
closes (on a merged PR the assignee stays — on a closed issue it records who did the work).
GitHub deletes the branch after merge. What is left: switch the draft to ready for review.

## 7 · What stays after this session ends

The last step, and **the default answer is "nothing"**. Writing everything down is how
the system rots: after thirty runs there are sixty notes contradicting each other.

For each finding ask one question — *what makes this class of defect not come back?* — and
answer with the strongest item that fits. The order is not arbitrary: a guard needs no
recall, prose does.

| Kind of finding | Where it belongs | Why not one row lower |
|---|---|---|
| A machine can check it | **guard** (test or `check_repo` check — skill `guard`) | zero recall cost, protects whoever comes next |
| The invariant was in the repo, just not found | **docstring/comment at the point of contact**, or a guard | the lookup failed, not the knowledge — text goes where one runs into it |
| Machine, environment, or the user's preference | **memory** | the repo cannot carry it |
| The order of steps failed | **the project overlay** `.claude/kit/<skill>.md` | it is workflow, not knowledge; your memory protects no colleague |
| Truly one-off | **nothing** | see above |

**Memory is the last resort, not the first.** Most defects a review finds have their answer
written in the repo already, in the very file being edited; no memory would have caught
them — there are hundreds of invariants, each in its file. **Prose does not enforce
itself** — that is why it becomes a guard. And the other way round: whatever in memory can
be expressed as a guard moves into the repo, and the note is deleted.

## Abandoning a task unfinished

Close the PR (the workflow removes label and assignee), delete the remote branch, and write
in the issue why. A claim without a commit for more than seven days may be released by
anyone after a comment.
