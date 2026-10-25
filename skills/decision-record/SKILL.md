---
name: decision-record
description: Write a decision record in docs/decisions/ — header block (Status/Parent/Origin/Scope with an explicit "does NOT"), the question, considered options with their cost, the decision, consequences and what it leaves undecided; or extend an existing decision with a dated addendum or a superseding record instead of rewriting it. Registers the record in docs/index.md and touches a CLAUDE.md rule only when the rule itself changes. Use whenever a choice between paths with different cost has been made or is being made. Triggers: "zapíš rozhodnutie", "zapiš rozhodnutí", "decision record", "ADR", "rozhodli sme", "dodatok k rozhodnutiu", "toto treba rozhodnúť".
---

# Decision record

A decision record keeps **why** the repo looks the way it does, so that the next person
tempted to undo it meets the argument instead of repeating the debate. It is the one home
of that argument: rules, skills and code link to it, they do not restate it
(`docs/documentation-principles.md`).

## 0 · Project overlay

Read `.claude/kit/decision-record.md` if it exists, before anything else; it wins on
conflict.

## 1 · New record, addendum, or superseding record?

Look first: `ls docs/decisions/` and grep for the topic. Then:

- **Nothing covers it** → new file `docs/decisions/<kebab-slug>.md` (ASCII, in the
  documentation language of the project). Open questions may be numbered
  (`oq1-<slug>.md`), batch reviews dated (`oq-review-YYYY-MM-DD.md`).
- **A record covers it and the new decision refines or extends it** → an **addendum** at
  the end of that record: `## Addendum N · YYYY-MM-DD — <one line>` (translated into the
  documentation language, numbering continues). Update the `Status:` line with a short
  "amended YYYY-MM-DD (addendum N: …)".
- **The new decision reverses it** → a **new** record; flip the old record's status to
  `superseded` with a link to its successor, and link back. The old text stays as it was.

**A decision is never edited into a different decision.** Rewriting the reasoning in place
erases what was chosen between and why — exactly what the next reader needs.

## 2 · Shape

```markdown
# <Title — the decision in words, not the topic>

> **Status:** decided · YYYY-MM-DD      (live / decided / brainstorm / superseded)
> **Parent:** [../index.md](../index.md)
> **Origin:** <session, brainstorm, incident, review — with a link when it exists>
> **Scope:** <what it governs>; does NOT <the explicit boundary>

## Question
What has to be decided and why now. One paragraph; the trigger in one sentence.

## Considered options
### A · <name>
What it is, what it costs (effort, risk, reversibility, who pays), what it buys.
### B · …

## Decision
The chosen option and the deciding argument. Say which consideration tipped it —
the hard case, the measurement, the boundary condition — not only that it is "better".

## Consequences
What changes in the repo, which rule or skill must follow, what becomes a guard,
what new cost is accepted knowingly.

## What this does not decide
The adjacent questions left open, so nobody reads the record as broader than it is.
```

Rules of the text:

- **Options carry cost.** An option without a stated cost is a strawman.
- **Rejected options keep their reasons** — "rejected because …" is what stops the same
  proposal next month. When something cannot be enforced by a machine, say so and why, so
  the next person tempted to write that guard meets the argument.
- **Measurements over impressions**, with date and method when they decide.
- **Open questions** stay listed with the item that owns them; when closed, they stay
  written and point at the addendum that closed them.

## 3 · Wire it in

1. Register a new record in `docs/index.md` (`| Document | What you'll find there |`).
2. **CLAUDE.md only when a rule changes.** Then the rule states the rule in one or two
   sentences and **links** the record — it never retells the argument. A decision that
   changes no rule does not appear in CLAUDE.md at all.
3. If the decision creates work, that work is a backlog item (`bl-start`); the record
   links it, and the item's `source:` names the record.
4. If the decision is checkable by a machine, the guard comes with it (skill `guard`);
   the record says "Guarded by <path>", or "nobody guards this — it stays with review".
5. Run `python3 scripts/check_repo.py` — it checks the header block and every relative link.

## 4 · Commit

`docs(decisions): <the decision in a few words> — BL-NN` (the item that carried the
decision; a decision without an item uses the PR's `nojira` path only when nobody else
could be deciding the same thing).
