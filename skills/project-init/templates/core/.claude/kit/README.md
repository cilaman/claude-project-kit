# Project overlays of the `project-kit` skills

The workflow skills come from the Claude Code plugin `project-kit` and are the same in
every repository that uses it. This directory is where **this** project extends them.
Each plugin skill reads its overlay **first** when it exists, and the overlay wins on
conflict.

| Overlay file | Extends plugin skill | Typical content |
|---|---|---|
| `bl-start.md` | `project-kit:bl-start` — claiming a task | extra preconditions, review triggers specific to this codebase |
| `bl-finish.md` | `project-kit:bl-finish` — closing a task | extra DoD gates, screenshot viewports, review dimensions |
| `bl-bug.md` | `project-kit:bl-bug` — filing a finding | shape of this project's bug reports, where logs live |
| `steward.md` | `project-kit:steward` — PR to green | verification commands, structural guards that are written decisions |
| `decision-record.md` | `project-kit:decision-record` | local conventions for decision records |
| `guard.md` | `project-kit:guard` — prose to guard | where guards live, shared helpers and markers |

Create an overlay only when there is something to say; a missing file means "the plugin
skill as is".

## What belongs here — and what does not

- **Here:** lessons about the **workflow** of this project — a step that was done in the
  wrong order, a gate the plugin cannot know, a command that differs here. Write the rule
  and, in one sentence, the incident that taught it.
- **Not here:** invariants of the **domain or the code**. Those become a guard (a test or
  a `scripts/check_repo.py` check), or a docstring at the place where one runs into them.
  An overlay is prose, and prose does not enforce itself.
- **Not here either:** facts about one machine or one person's preferences — those are
  memory of the session, not of the repo.

A lesson that would help every project using the kit belongs upstream, in the plugin.
