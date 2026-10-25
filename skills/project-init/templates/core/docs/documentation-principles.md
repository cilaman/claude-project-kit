# Documentation principles

> **Status:** decided · {{TODAY}}
> **Parent:** [index.md](index.md)
> **Origin:** initialisation from project-kit
> **Scope:** the method of documentation (principles, header blocks, decision records, comments and docstrings in the source); does NOT decide the content of individual documents

## Four principles

1. **One fact = one home.** Every fact has exactly one authoritative document; the
   others link to it instead of restating it.
2. **Explicit responsibility.** Every document declares in its header what it governs
   and what it explicitly does NOT cover.
3. **Links both ways.** A parent and a child document link each other.
4. **Map over search.** [index.md](index.md) is a table routing the reader to every
   document: `| Document | What you find there |`. `scripts/check_repo.py` fails on a
   document the map does not link.

## Header block

Every document starts with an H1 title followed by a blockquote:

```markdown
# <Title>

> **Status:** decided · 2026-01-31     (vocabulary: live / decided / brainstorm / superseded)
> **Parent:** [parent.md](parent.md) · doc-set: [index.md](index.md)
> **Origin:** <how the document arose — session, brainstorm, incident>
> **Scope:** <what it governs; including an explicit "does NOT …" boundary>
```

An update is appended to the Status line with its date and one clause about what
changed — the document stays one home, the history stays visible.

## Decision records (`docs/decisions/`)

- One file = one decision, kebab-case; template [decisions/_TEMPLATE.md](decisions/_TEMPLATE.md).
- Structure: header block → `## Question` → considered options with their cost →
  `## Decision` → `## Consequences` → `## What this does not decide`.
- A decision is never rewritten into another one. A refinement is a dated
  `## Addendum N · YYYY-MM-DD — <one line>`; a reversal is a new file and the old one's
  status flips to *superseded* with a link.
- The skill `decision-record` writes them.

## Comments and docstrings

**A comment carries the reason and the invariant, not the history of the code.** That
something moved, was renamed or used to be different is held by the commit and by
`backlog/done/`. A `BL-NN` reference is fine — the number is an address, not a changelog.

The boundary is one question: **does the sentence teach something about today?**

```python
# ✅ reason: the past is there as evidence, the sentence holds for today's code
# Both conditions sit in one `filter()` on purpose: applied to the same related row,
# a name that matches belongs to the owner who did not sell. Split into two calls
# they are met by two different rows.

# ❌ changelog: says nothing about how to read the code
# This function lived in `selectors.py` until BL-129 and moved here.
```

**A docstring is not longer than its body without a reason.** Sometimes the reason
exists — a rule of law, an invariant three lines of code do not show — and then a long
docstring is right. Review guards this, not a machine: whether a sentence teaches
cannot be decided by a regular expression.
