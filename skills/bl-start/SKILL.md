---
name: bl-start
description: Start work on a backlog item — create or take over the GitHub issue (its number IS the item id BL-NN), decide whether a spec file is needed, claim the task with a pushed claim commit and open a draft PR with `Closes #NN` filled in. Use whenever work begins on anything that will end in a pull request — a BL-NN item, a bug, a cleanup, even a one-line fix. Triggers: "vezmi si BL-…", "zaber úlohu", "začni na tomto", "urob issue #…", "take BL-…", "start on this task", "claim it".
---

# Claiming a backlog item

The protocol of CLAUDE.md (the claim rule) and of
[docs/decisions/task-tracking.md](docs/decisions/task-tracking.md). The order is binding
and **is not skipped for a "small" fix** — small fixes are exactly where two sessions
collide, because nobody thinks a claim is worth it.

## 0 · Project overlay

Read `.claude/kit/bl-start.md` if it exists, before anything else. It extends this page
for this project and wins on conflict. Lessons about this project's *workflow* belong
there, not here.

## 1 · How you talk to GitHub

Find out now, not at the step that needs it:

```bash
which gh && gh auth status
```

Without `gh` (remote sessions typically lack it) use the `mcp__github__*` tools —
`issue_write`, `issue_read`, `list_issues`, `create_pull_request`. With neither, **create
nothing blind** and say so: without an issue the task has no number and the claim has
nothing to hold on to.

## 2 · Issue — the server assigns the number

**New work:** create the issue (`.github/ISSUE_TEMPLATE/task.yml`, a defect `bug.yml`).
The number returned **is** `BL-NN`. Never guess "the next free number" from the backlog —
two sessions guessing on the same day produce two items with one id.

**Existing item:** check nobody holds it — the issue must be open, must not carry
`in-progress`, and no open PR may point at it. **A claimed task is not taken over:** pick
another one, and if you need exactly that one, write in the issue.

Check `depends_on:` in the spec file too — a task standing on unfinished work does not start.

**Do not open `backlog/BACKLOG.md` to orient yourself.** Grep the register; it returns the
matching lines instead of a whole document:

```bash
grep '^BL-118' backlog/tasks.tsv   # status, priority, parent, depends_on, uc, path, title
grep 'UC-30'   backlog/tasks.tsv   # which task owns a use case
```

The real record of an older task is its file in `backlog/done/` (path in the last
columns of the register), not the archive digest in `backlog/DONE.md`.

## 3 · Spec file only when a design is needed

`backlog/BL-NN-kebab-slug.md` (ASCII, from `backlog/_TEMPLATE.md`) is created **only** when
at least one holds:

- the solution is being decided (several paths with different cost),
- it touches several modules,
- it has its own DoD beyond "tests green".

Otherwise the item lives as the issue alone. When the file is created, add the
`needs-spec` label and link the file from the issue body. Front-matter keys keep their
fixed order (CLAUDE.md, `backlog/_TEMPLATE.md`); **an item born from a defect claims no
use case** (`uc: —`) — it restores promised behaviour, it does not deliver new.

## 4 · The claim is a pushed branch with its own commit

```bash
git checkout -b bl-176-kebab-slug
git commit --allow-empty -m "chore(backlog): claim — <title> — BL-176"
git push -u origin bl-176-kebab-slug
```

**A bare branch does not hold the claim.** Two actors branching from the same commit push
the identical sha, and the second gets "Everything up-to-date" and exit 0. With its own
commit the second push ends in `rejected (non-fast-forward)` — that rejection is the whole
safeguard. If the push fails, someone has the task: **do not force it**, take another.

**When the branch name is dictated from outside** (a remote session gets `claude/…` and may
push nowhere else), use it and write the reason into the claim commit. The commit holds
the claim, not the shape of the name; labels derive from the PR, not the branch.

## 5 · Draft PR now, with the number

Open the **draft PR at the start, not at the end** — it shows others the claim and what is
already done. In the description write the number: `Closes #176`, not a bare `Closes #`.

That line does three things: the merge closes the issue with it, the workflow
`task-lifecycle.yml` derives the `in-progress` label and assignee from it, and the step
**`PR names its issue`** fails CI without it. A bare `Closes #` once got merged and the
issue had to be closed by hand — the mechanism exists because goodwill did not hold.

**A task with a spec file may leave it out** — once you move the file into `backlog/done/`
the workflow derives the number from that move and writes it into the description. **A bug
or cleanup without a file must have it written:** nothing in its diff names the issue.

A change that needs no backlog item at all passes with the label **`nojira`** on the PR
instead. Label and number are mutually exclusive (a PR with both is red), and `nojira`
**holds no claim** — whatever someone else could also be doing belongs to an issue.

## 6 · Label and assignee — leave them alone

The workflow puts them on from the PR description and takes them off when the PR closes.
A manual `--add-label in-progress` is a second writer of the same fact; two writers of one
fact are how the queue drifted before.

## 7 · Decide now whether this needs the expensive review

Not at the end — at the end it no longer fits, and gets run after the finish line. Two
triggers, one is enough:

**First of its kind.** The first table in a module, the first component in the shell every
screen carries, a new registry, a new global shortcut. **Where something is first,
existing guards cannot reach it** — there was nothing to write them over yet.

**A semantic change somebody builds on.** Not the interface — the meaning. When one half
of a pair changes what it means (search goes from one needle to many words) and the other
half (highlighting) is not told, the result passes every existing test.

When neither trigger holds, the expensive review is not run — on a flaky-test fix it is an
hour of tokens for nothing, and real findings drown in the noise. Ceremony proportional to
the question. When a trigger holds, note it in the draft PR in one sentence; `bl-finish`
says how the review runs and what happens to its findings.

When the work is done: skill `bl-finish`. Between the two, getting the PR green: `steward`.
