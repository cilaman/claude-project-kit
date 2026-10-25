# Task tracking — backlog in the repository, identity and claim in GitHub

> **Status:** decided · {{TODAY}}
> **Parent:** [../index.md](../index.md)
> **Origin:** adopted at initialisation from project-kit — the method of a previous project, distilled with the incidents that shaped it
> **Scope:** which fact about a task lives in the repository and which in GitHub, how a task is claimed and closed, where bugs live, what is generated, and how ceremony scales with the change; does NOT decide the content of individual tasks, the CI test matrix, or the Definition of Done of the code (CLAUDE.md)

## Question

How do a person and several parallel AI sessions share one backlog without colliding,
without two homes for one fact, and without the backlog itself becoming the most
expensive thing to read?

## Decision

### 1. Split by kind of fact

**The repository owns "what, why and whether it is done". GitHub owns "who, and what
right now".**

| Fact | Home | Why there |
|---|---|---|
| Identity of the item, discussion, claim, assignee | GitHub issue | the only fact that needs a shared real-time server |
| Specification (context, goal, steps, DoD) | `backlog/BL-NN-*.md` | reviewable in a PR, versioned with the code, readable offline |
| State (`status:`), priority, dependencies | front matter of the spec file | generators and checks must run without the network |
<!-- kit:if requirements -->
| Link to a use case (`uc:`) / requirement (`parent:`) | front matter of the spec file | same — the catalog state is derived from it |
<!-- kit:endif -->
| Bug or cleanup without a design | issue only, no file | that is the whole point of the second level of ceremony |

Sync goes **one way: repository → GitHub.** Closing an issue is a *consequence* of the
merge (the spec file moved to `done/`), never a second write of the state.

### 2. The number of an item is the number of its issue

`BL-NN` ≡ issue `#NN`. The server is the only atomic allocator there is; two sessions
picking "the next free number" by reading the backlog collide on the same day. The
series is not contiguous (pull requests share the counter) and that is fine.

### 3. A spec file only when a design is needed

A bug is filed as an issue immediately and without ceremony. A file
`backlog/BL-NN-slug.md` is written when **at least one** holds: the solution is being
decided (several ways at different cost), it reaches into several modules, or it has
its own DoD beyond "tests green". Promotion is one-way: the issue gets the
`needs-spec` label and a link to the file; a file once written is never deleted —
a cancelled item becomes `OBSOLETE` in `done/`, because why something is not done is
history too.

### 4. A claim is a push of a branch with its own commit

`gh issue edit --add-assignee` is last-write-wins. The atomic primitive available for
free is **pushing a new remote branch**: it fails against an existing one. **A bare
branch holds nothing** — two actors branching from the same commit push the same sha
and the second gets "Everything up-to-date" with exit 0. With a claim commit of its
own, the second push is rejected as non-fast-forward. A session whose branch name is
dictated by its environment uses that branch and writes the reason into the claim
commit; the claim is the commit, not the shape of the name.

### 5. The pull request carries the lifecycle

`Closes #NN` **with the number** in the PR description does three things: the merge
closes the issue, the `task-lifecycle` workflow puts `in-progress` and the assignee on
it (and takes them off when the PR ends), and its first step fails while the number is
missing. A spec file arriving in `backlog/done/` already says which issue the PR
finishes, so the workflow **derives the number and writes it in**; a bug without a file
leaves no trace in the diff, so there the author writes it. **Nobody closes an issue a
second way** — two paths to one write are two places for it to drift.

The direction "closed task ⇒ closed issue" is checked **only on the main line**: on a
branch the file moves before the merge closes the issue, and a guard red on every
finished PR teaches people to ignore it. The satisfiable mirror — "a PR ready for review
has its task in `done/`" — is checked on the PR, drafts excepted.

### 6. What is computable is not typed

The active section of `backlog/BACKLOG.md`, the register `backlog/tasks.tsv` and the
archive `backlog/DONE.md` are written by `scripts/check_repo.py`; a hand edit fails CI.
The order of the index is derived from `depends_on:` (a task never stands above what it
stands on), then priority, then number. The archive row comes from `result_note:`, so
the sentence about the outcome is typed once and lives with the task. The register
exists so that "what is BL-NN" is a grep, not a document read; the archive is separate
so that reading the active backlog does not cost reading its whole history.

A merge conflict in a generated file is never resolved by hand: take the main line's
side and regenerate from the task files.

### 7. Ceremony proportional to the change

A trifle that needs no backlog item passes with the **`nojira` label on the PR** — a
label because it comes on and off without a push, while a keyword in a commit message
is read by no guard at all. The label and a number exclude each other. **It holds no
claim**: whatever somebody else could also be doing belongs to an issue.

<!-- kit:if ci-savings -->
How much of the test suite runs is **derived from the diff**
(`scripts/ci_scope.py`), never declared by a keyword — a keyword can skip the tests of a
change to the source, which is the one case where skipping is dangerous. "Only
documentation" is not the dividing line: tests read documentation, and the lists of
paths nobody reads are kept honest by a test.
<!-- kit:endif -->

### 8. What the sieves are

Green tests catch the invariants somebody already wrote down as a guard — nothing else.
Before "done": screenshots before and after for anything a screen shows; an adversarial
review when the change is the **first of its kind** (no guard can exist yet) or **changes
semantics somebody builds on**; and every test written in the task is **mutated** to
prove it can fail. A defect found after a green DoD gets the `escaped-dod` label and one
line naming the sieve that should have caught it.

### Commits

`type(scope): description — BL-NN`, types `feat`, `fix`, `test`, `docs`, `chore`,
`refactor`, `ci`. The claim commit is `chore(backlog): claim — <title> — BL-NN`. Every
substantive commit references its item, also one without a spec file.

## Consequences

- `gh` (or the GitHub MCP tools) is a precondition of a working session: without it
  neither the bug queue nor the claim is visible.
- Offline work stays possible for everything but claims and bugs.
- The skills `bl-start`, `bl-finish`, `bl-bug` and `steward` (project-kit) run the
  protocol; project-specific lessons about it go to their overlays in `.claude/kit/`.

## What this does not decide

The labels' vocabulary (`.github/labels.yml` is its home), the content of the Definition
of Done (CLAUDE.md), and the review process beyond the sieves named above.
