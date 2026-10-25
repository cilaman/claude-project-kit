---
name: guard
description: Turn an invariant that lives only as prose (a rule in CLAUDE.md, a decision, a docstring, a review finding) into a machine guard — a test or a `check_repo.py` check — with an anti-vacuum test, the reverse direction (named exceptions with reasons, where empty and orphan rows fail), a mutation proof that it really fails, and the rule text wired to "Guarded by <path>"; and say out loud what stays unguarded. Use after a defect class was found, when a rule is added, or when someone asks the invariant to be enforced. Triggers: "sprav z toho stráž", "pridaj test na pravidlo", "aby sa to nevrátilo", "ohlídej to testem", "guard", "invariant", "enforce this rule".
---

# From prose to a guard

**Prose does not enforce itself.** Most defects a review finds already had their answer
written in the repo, in the file being edited — and nobody read it at the moment it
mattered. A guard needs no recall. A rule without a guard is an aspiration; prefer writing
the guard.

## 0 · Project overlay

Read `.claude/kit/guard.md` if it exists, before anything else — it says where this
project's guards live and which helpers they share. It wins on conflict.

## 1 · Find the one home of the invariant

Before writing code, state the invariant in one sentence and find where it is written:
a CLAUDE.md hard rule, a decision record, a docstring. If it is written in two places,
fix that first (one fact = one home). The guard's docstring **links** that home and
states the failure it prevents — the concrete shape, not "keeps things consistent".

Choose the place, weakest sufficient first:

- **a rule of `architecture.toml`** (when the project has it) — a layer boundary, a
  construct forbidden in some paths, a declared skip. Textual, works for every language,
  costs one entry. Enough when the invariant is visible in the words of the code.
- **a stack-native test** — when the words are not enough: an import built at run time,
  a write behind a helper, a property of the database schema, an attribute of a type.
  Written in the project's own test framework and language; structural tests read the
  syntax tree or the files rather than running the code, so a violation is caught even
  in code no test calls.
- **a check in `scripts/check_repo.py`** — an invariant over repo structure, docs or
  backlog (stdlib only, must stay green offline).

## 1a · Stack-native guards — the recurring shapes

The invariants worth a guard are the same in every stack; only the API that reads them
differs. For each, ask the stack for the **structure**, not the behaviour:

| Invariant | What the guard reads | Shape in one stack (worked example) |
|---|---|---|
| A layer does not reach a layer it must not know | the import graph (AST, compiler, module resolver, ArchUnit, dependency-cruiser, go list) | `references/python-django/tests/structure/test_layering.py` |
| A place does not write the database | calls in that place's syntax tree | `references/python-django/tests/structure/test_writes.py` |
| Tenant data is isolated by the database | the database catalog after migrations (policies, constraints, grants) — never the ORM's opinion of it | `references/python-django/tests/tenancy/test_rls_policies.py` |
| Everything linked to X is classified | the model/type registry, in **both** directions, with a named-exceptions dictionary | the reverse half of `test_rls_policies.py` |
| Every skip is a decision | the test files' syntax tree | `references/python-django/tests/structure/test_skips.py` |
| Identifiers follow the language policy | names defined in the syntax tree | `references/python-django/tests/structure/test_language_policy.py` |

The references are **one stack's answer**, kept for their shape — anti-vacuum, reverse
direction, exceptions with reasons, a catalog query instead of trusting the framework.
Translate the shape to the project's stack (e.g. ArchUnit for layering on the JVM,
`ts-morph`/dependency-cruiser in TypeScript, `go/packages` in Go, a `pg_policies` query
from any language); do not copy the Python.

## 2 · Write the guard with its anti-vacuum

A guard that walks an empty set passes on nothing, and looks exactly like one that passed.
Every guard gets two companions:

1. **The set is not empty** — the list of modules, models, files or rows it iterates has
   members; if it can legitimately become empty, that is a decision someone writes down,
   not something that quietly becomes true.
2. **The detector finds a synthetic violation** — feed it a small hand-written source or
   fixture that breaks the rule and assert it is reported (and that a near-miss is not:
   a dict's `.update()` is not a database write). This proves detection without needing a
   violation in the repo.

Also check the guard looks for **what the code really spells today** — if the string or
name it matches is renamed, the guard stays green over a literal nobody writes any more.
Pin that name with its own assertion.

Error messages say what to do: the rule, the file, and the fix ("add X to the migration",
"move the write into the service").

## 3 · The reverse direction

A registry derived from one fact guards only one direction. "Every model inheriting from
the tenant base has a policy" says nothing about a model linked to the tenant that does
**not** inherit — it falls through every test without a mention.

Add the opposite check, and where the answer is legitimately "no", an **exception
dictionary**: `{name: reason in prose}`. Three rules make it a decision instead of a hole:

- an entry **without a reason** fails — a bare list says someone once looked, not why,
- an **orphan** entry (no longer matches anything) fails — a stale exception covers what
  nobody checked again,
- an **empty** dictionary fails when the category should exist — someone emptied it, or
  the guard no longer finds what it looks for.

Silence is not a decision: everything is either compliant or named with its reason.

## 4 · Mutation proof

Your new guard is the only one in the repo nobody knows protects anything. Prove it:

1. change one expression in the **source** the guard protects (or remove half of a
   condition),
2. run only that test — **it must fail**, with the message you wrote,
3. revert, and check `git diff` is clean.

Especially for **textual** guards (over JS, CSS, docs): they check words, not behaviour,
and can pass because the word survived elsewhere in the file. Avoid asserts that cannot
fail: over a **set** (order is invisible — use a list in deliberately wrong order), over
two copies of the same input, or over a field that is not the only thing deciding the
verdict in the tested state.

## 5 · Wire it into the rule

- The CLAUDE.md hard rule (or the decision record) ends with **"Guarded by `<path>`."**
- If part of the rule cannot be checked by a machine, say it explicitly in the rule:
  **"Nobody guards X — it stays with review."** Naming the gap is what stops the next
  person from believing it is covered, and from re-attempting an impossible guard.
- If a list in a guard is a claim about the whole repo (e.g. "paths no test reads"), it
  needs its own guard, or it is true only on the day it was written.

## 6 · Finish

Run the full Definition of Done (the new guard may find existing violations — fix them or
name them as exceptions with reasons, never weaken the guard to pass). Commit as
`test(<scope>): guard — <invariant> — BL-NN`. If the invariant came from a memory note,
delete the note: it now lives in the repo.
