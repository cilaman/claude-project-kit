# Backlog

> 1 file = 1 task that needs a written design (`BL-NN-kebab-slug.md`, `BL-NN` = issue
> number); closed tasks move to `done/`. Template: [_TEMPLATE.md](_TEMPLATE.md).
> Bugs and cleanups without a design live only as GitHub issues.

## Active tasks

<!-- generated: active-tasks -->
<!-- /generated -->

> **The table above is generated — never edit it by hand.**
> `python3 scripts/check_repo.py --rebuild-backlog` writes it from the front matter of
> the task files; a hand edit fails CI. **The order is derived, not agreed:**
> topologically by `depends_on:`, within a layer by `priority:` and then number. Whoever
> wants a different order changes `depends_on:` in the task file.

<!-- Dated notes about how a batch of tasks arose go below, linking their decision:
> **YYYY-MM-DD:** BL-NN…BL-MM arose from <decision/brainstorm>, see docs/decisions/<file>.md.
-->

## Status legend

🆕 NEW · 🔵 IN_PROGRESS · 🟡 NEEDS_INPUT · 🟠 BLOCKED · 🟢 DONE · ⚪ OBSOLETE

Closed tasks: [DONE.md](DONE.md). For one task, grep the register:
`grep '^BL-NN' tasks.tsv`.
