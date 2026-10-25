# Initialisation prompt (without the plugin)

Paste the block below into a Claude Code session opened in the new repository. It assumes
the kit is checked out at `~/Private/Projects/claude-project-kit`; change the path if not.
With the plugin installed, `/project-kit:project-init` does the same.

---

```text
Initialise this repository with the project-kit method.

The kit is at ~/Private/Projects/claude-project-kit. Read, in this order:
1. METHOD.md — the method and why each rule exists,
2. skills/project-init/CONVENTIONS.md — the names every piece shares,
3. skills/project-init/SKILL.md — the order of work; follow it step by step.

Rules for this run:
- Render templates only with skills/project-init/scaffold.py (dry run first); never
  copy templates by hand.
- Ask me only what you cannot derive from the repository (name and one-paragraph
  description, documentation language, optional layers: requirements / ci-savings /
  architecture, the toolchain and the setup / test / lint / regression commands, and the
  non-negotiable invariants of the domain — each becomes a hard rule with a guard).
- Code is English; translate the prose of the rendered docs into the documentation
  language, never keys, statuses, markers, flags, label names, step names or file names.
- Every hard rule in CLAUDE.md names its guard or says nobody guards it.
- Finish with `python3 scripts/check_repo.py --no-issues` and
  `python3 -m unittest discover -s tests/scripts -t .` green.
- Ask before anything outward-facing: applying labels to GitHub (the vocabulary is
  complete and deletes GitHub's defaults), pushing, opening PRs.
- Since the plugin's workflow skills are not installed, copy skills/bl-start,
  skills/bl-finish, skills/bl-bug, skills/steward, skills/decision-record and skills/guard
  from the kit into .claude/skills/ of this repository, and say so in the report.
```
