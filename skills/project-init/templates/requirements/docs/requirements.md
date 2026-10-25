# Business requirements (RQ)

> **Status:** live · {{TODAY}}
> **Parent:** [index.md](index.md)
> **Origin:** initialisation from project-kit
> **Scope:** rules of the requirement layer (when a requirement is born, where membership lives, how its state is derived) and the **generated** list of requirements; the prose and acceptance of one requirement live in [requirements/](requirements/), membership only in the `parent:` key of a backlog item; does NOT describe behaviour ([use-cases.md](use-cases.md))

A task carries work, the catalog [use-cases.md](use-cases.md) carries behaviour — and
the question **"when is it fulfilled"** is carried by this layer: one document per
requirement with its prose and written acceptance, and below it the backlog items that
work it off.

## How the layer works

- **Two levels, not three.** A requirement `RQ-NN` and below it items `BL-NN`. A piece
  that needs its own owner and claim is a **sibling under the same requirement**, not a
  new class of identifiers.
- **One file = one requirement**, `requirements/RQ-NN-kebab-slug.md`, numbered by hand
  from `RQ-01`; ids are never changed or reused. Template:
  [requirements/_TEMPLATE.md](requirements/_TEMPLATE.md).
- **Membership has one home: `parent: RQ-NN`** in the front matter of the item. A
  `parent:` naming a requirement without a document is an error.
- **The list of items is never typed.** The table below is generated:
  `python3 scripts/check_repo.py --rebuild-requirements`.
- **State is derived, fulfilment is not.** `delivered` means "all items done", **not**
  "the acceptance holds". A person confirms the acceptance against the document and
  writes it there.
- **When a requirement is not born:** when it would only repeat an area of the
  catalog, when it has a single item, or when its acceptance would read "when the items
  are done" — that is a tautology, not an acceptance.

## Requirements

<!-- generated: requirements -->
<!-- /generated -->
