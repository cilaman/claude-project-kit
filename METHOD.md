# The method

How a repository stays coherent when a person and several parallel AI sessions work on it
at once. Distilled from a project that ran it for months; every rule below exists because
its absence once cost something. The kit's templates, scripts and skills implement it —
this page says **why**, [CONVENTIONS.md](skills/project-init/CONVENTIONS.md) says **with
which names**.

## 1 · Every fact has one home

- **One fact = one home.** Every other place links to it. Two homes drift, and the
  reader cannot tell which one is stale.
- **Every document declares its scope**, including what it does *not* govern — the header
  block `Status / Parent / Origin / Scope`.
- **Map over search.** `docs/index.md` routes to every document; a document the map does
  not link fails the check.
- **Decisions are never rewritten.** A refinement is a dated addendum, a reversal a new
  record that supersedes the old. The history of *why* is the part a later reader needs.
- **Comments carry reasons and invariants, not history.** "Moved here in BL-129" is noise;
  "both conditions sit in one filter because …" is the most valuable line in the file.

## 2 · The repository owns *what and why*; GitHub owns *who and now*

- A backlog item `BL-NN` **is** GitHub issue `#NN`. The server is the only atomic number
  allocator; sessions guessing the next free number collide on the same day.
- Specification, state, priority, dependencies live in the **front matter** of the spec
  file — versioned with the code, reviewable in the PR, readable offline. Claim and
  assignee live **only** in GitHub. Sync goes one way: repository → GitHub.
- **Ceremony scales with the change.** A bug or a cleanup is an issue only. A spec file
  exists when the solution is being decided, the change spans modules, or it has its own
  DoD. A requirement (`RQ-NN`) exists when acceptance has to be written down. A trifle with
  no item at all passes with the `nojira` label — and holds no claim.

## 3 · A claim is a push, not a promise

1. Issue first — the number. 2. Push `bl-NN-slug` **with its own claim commit**; a bare
branch is the same sha for two actors and the second push "succeeds" silently. 3. Draft PR
immediately, `Closes #NN` with the number. 4. Label and assignee are derived from the PR by
a workflow, never set by hand. 5. The merge closes the issue — nothing else does.

The spec file moves to `done/` **inside the branch, before ready for review**; the workflow
derives `Closes #NN` from that move. "Closed task ⇒ closed issue" is checked only on the
main line, because on a branch it is unsatisfiable — and a guard that is red on every
finished PR teaches people to ignore guards.

## 4 · What is computable is never typed

The active index, the archive, the machine-readable register, requirement and use-case
states are **generated** from front matter. Hand edits fail CI (and are refused by the
kit's hook). Consequences that turned out to matter:

- **The register (`tasks.tsv`) makes "what is BL-NN" a grep**, not a 250 kB read — for an
  AI session, reading cost is the dominant cost of orientation.
- **The archive is apart from the active index** for the same reason.
- **Order is derived** from `depends_on:` (topological, then priority) — the old habit of
  ordering rows by hand carried a fact nobody could check.
- **A merge conflict in a generated file is never resolved by hand:** take the main
  line's side, regenerate from source.
- **State is derived, fulfilment is not.** "All items done" is not "acceptance holds";
  a person confirms acceptance against the written requirement.

## 5 · A rule is as strong as its guard

- Each hard rule in `CLAUDE.md` names **the test that guards it**, or says out loud that
  **nobody guards it** and it stays with review. A rule with neither is an aspiration.
- **Anti-vacuum:** every guard also asserts that the set it walks is non-empty and that its
  detector finds a synthetic violation. A guard over an empty list is green forever.
- **Both directions:** a registry derived from inheritance guards only its members. The
  reverse guard ("everything linked to the organization is tenant data **or named, with a
  reason**") catches what fell outside. Silence is not a decision; an exception without a
  reason, or one that outlived its code, fails.
- **Every skipped test is declared** with who answers the question instead — a skipped
  test is the one failure that reports success.
- **Two strengths of guard.** A textual guard (`check_architecture.py`: imports, forbidden
  constructs, skips) works for every language and costs one line of configuration; a
  stack-native guard (syntax tree, compiler, the database catalog) sees what words cannot.
  Use the weakest that suffices, and say which one guards what.

## 5a · The method is not a stack

Nothing in the method depends on the language, framework or database. The stack enters
in exactly three places, each with one home: the **commands** of the Definition of Done
(CLAUDE.md), the **toolchain** CI sets up (`.github/actions/setup-toolchain`), and the
**native guards** of the project's non-negotiable invariants. The fixed technology is
only what the process itself runs on: GitHub (issues are the identity, Actions the
lifecycle) and Python 3.11+ for the standard-library process scripts.

## 6 · Green tests are the weakest sieve

Tests catch what someone already wrote down as a guard — nothing else. Before "done":

- **screenshots before and after** for anything a screen shows (geometry nobody measures),
- an **adversarial review** — several reviewers by dimension and an adversarial verifier
  per finding — when the change is **first of its kind** (no guard can exist yet) or
  **changes semantics somebody builds on**; otherwise not, because noise drowns findings,
- **mutation of every test written in the task**: break the source, see the test fail,
  revert. A textual guard can pass over the very defect it was written for.
- A defect found after a green DoD gets `escaped-dod` and one line: which sieve should have
  caught it. That query says where to invest next.

## 7 · Where a lesson goes — default "nowhere"

| Finding | Home |
|---|---|
| A machine can check it | a **guard** |
| The invariant existed, it was not found | a **docstring at the point of contact** |
| Machine, environment, user preference | **memory** |
| The order of workflow steps failed | the project **overlay** of the skill (`.claude/kit/`) |
| One-off | **nothing** |

Writing everything down is how the system rots — sixty notes after thirty runs, half
contradicting the others. Memory is the last resort: most defects had their answer
written in the file being edited.

## 8 · CI is paid per started minute

- **Scope is derived from the diff, never declared by a keyword** — a keyword can skip
  tests on a source change, the one case where skipping is dangerous. "Only docs" is not a
  safe line: tests read docs. The lists of unread paths are kept honest by a test.
- Pessimistic by construction: an unreadable diff runs everything.
- Several checks share one job (`continue-on-error` + a final step that fails it): each
  job is billed rounded up to a minute, and the author still sees every failure at once.
- A merge re-testing a tree a PR just proved green is skipped by **tree hash**, not sha.
- The regression suite (asks about the environment, not the code) is outside the DoD and
  runs weekly — so the DoD stays satisfiable on any machine.

## 9 · Working with AI sessions

- `gh` may be missing in a remote session — the `mcp__github__*` tools do the same; with
  neither, create nothing blind.
- A remote session gets its branch name dictated (`claude/…`): the claim is the commit,
  not the name; workflows key on the PR, never on the branch name.
- Agents leave worktrees inside the repo — tree walks skip nested checkouts.
- Reviewers write probe files into the working tree — no `git add -A` during a review;
  parallel test runs need separate test databases.
- Procedures are **skills invoked by name**, not protocols retyped from memory; the
  project's lessons about them live in overlays next to the code they concern.
- The language policy is explicit: code English, docs in the project's language, and the
  list of what stays untranslated has one home.
