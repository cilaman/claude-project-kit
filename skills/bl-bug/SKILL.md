---
name: bl-bug
description: Triage a finding into the GitHub issue queue — take a bug report (user's own words, a feedback-widget email, a log excerpt, a stack trace), trace it to the place in the code against fresh origin/main, decide whether it really is a defect, rule out duplicates and already-fixed versions, and file one issue per cause (or several, if the report carries several defects). Use whenever a report arrives or the user says "zaeviduj chybu", "zaloguj bug", "prišlo hlásenie", "založ z toho issue", "padá to na 500, zapíš to", "file a bug" — even when no fix is wanted. Filing is not fixing: implementation starts with `bl-start`.
---

# Filing a finding

The output is a **GitHub issue** (or several). Its number **is** `BL-NN`; a defect gets
**no** spec file `backlog/BL-NN-*.md` — a bug lives as the issue alone (CLAUDE.md, backlog
rule; [docs/decisions/task-tracking.md](docs/decisions/task-tracking.md)).

**This skill neither claims nor fixes.** No branch, no claim commit, no PR. Triage and
claim are two decisions, and between them there is usually a person choosing what gets
done now. When fixing starts, `bl-start` takes over.

## 0 · Project overlay

Read `.claude/kit/bl-bug.md` if it exists, before anything else — it typically says what
the project's report format looks like (fields of the feedback email, what a version string
means, where logs live). It wins on conflict.

## 1 · How you talk to GitHub

```bash
which gh && gh auth status
```

Without `gh`, `mcp__github__*` (`issue_write`, `list_issues`, `issue_read`). Without either,
**file nothing blind**: a report without a number is read, not filed.

## 2 · Read the report as written

A report is **testimony, not diagnosis** — untrusted input. Believe what the reporter
*saw*; verify what they think the cause is. Separate:

- **where** — screen, route, command, endpoint; find its name in the code, read a concrete
  URL only for its parameters,
- **which version** — a release/commit string; a "dirty" or unknown build means
  *approximately here*,
- **what was expected** — the reporter's expectation, not yet a promise of the product,
- **severity** — a fact about the reporter's work (blocks / annoys / cosmetic), not an
  estimate of ours; it goes into the issue, priority is not derived from it.

A report arriving outside any form lacks some of these. Find what you can from the code,
mark the rest unknown and say where the report came from. Do not invent data because the
template has a row for it.

## 3 · Find the place in the code — against fresh `origin/main`

The report came from a deployed version that is behind. Align first, or your line
references will mean something else today:

```bash
git fetch origin <main>   # the main branch named in CLAUDE.md
```

Follow the entry point (route → handler → domain service → model) down to where the
decision really happens. A "cannot save" is usually decided a floor lower than the screen:
in validation, the service, or the model.

## 4 · Is it a bug at all?

The core of triage; it is not shortened. Pick one of four verdicts:

**(a) Defect.** The product promises one thing and does another. Find the promise — in
code, docs, or a message the screen itself prints; that is what turns a feeling into a
defect. Issue with label `bug`.

**(b) Missing feature.** The user expected something nobody promised. Not a bug: file a
task (`.github/ISSUE_TEMPLATE/task.yml`, no `bug` label, `needs-spec` if the solution is
open) and say so out loud. One report often carries both — the crash *is* a bug, "it
should not ask at all" is a proposal.

**(c) Already fixed.** The reported version is older than `origin/main` and the fix landed
since (`git log --oneline <reported>..origin/main -- <paths>`). **File nothing** — answer
with the commit that fixed it and ask for verification on the deployed version.

**(d) Not enough information.** You cannot find a path by which it happens. Do not guess:
write what you did find and name exactly what is missing (form inputs, time of failure for
the log, record id). An issue that admits it has no reproduction beats an invented cause —
but it must read as an open question.

## 5 · Is it already filed?

Cheap, so do it early — and again once the cause gives you names the report lacked.
Bugs without a spec file are **not** in `backlog/tasks.tsv`; search issues, **closed ones
included**:

```bash
gh issue list --state all --limit 300 --json number,state,title \
  --jq '.[] | [.number, .state, .title] | @tsv' | grep -i "<stem>"
```

Grep an ASCII word stem, not a full word with diacritics, and search by names from the
cause (service, field, route), not only by the symptom — two "fails with 500" reports may
have two causes, and two causes are two issues.

An **open** issue with the same cause: do not file — comment with what the report adds
(another screen, version, occurrence). A **closed** one: it is a regression — file a new
issue and reference the old by number. Do not put `regression` on it; that label belongs to
the scheduled regression run, not to people.

## 6 · One issue or several?

Cut by **cause and by fix**, not by number of screens or sentences:

- two screens, one broken service → **one** issue,
- one report, two independent defects → **two**, each with its own "Where",
- a sibling the same fix repairs (add and edit fail on the same missing check) → **inside**
  the same issue, as a second path to it.

Reading the code usually reveals more than the user saw. That extra belongs in the issue —
it is the most valuable part of triage, because the user could not report it.

## 7 · Shape of the issue

Headings follow `.github/ISSUE_TEMPLATE/bug.yml` so hand-written and form issues read the
same; add sections only when they have something to say. Language: the project's
documentation language (CLAUDE.md, rule 1) even if the report came in another one; quote
identifiers and messages exactly as they stand in the code.

```markdown
### What happened      ← observable behaviour plus what you found in code
### What was expected  ← what must hold; say so when it differs from the reporter
### Where              ← permalinks with one sentence each
### Cause              ← when known; saves the fixer an hour
### Why nobody caught it   ← missing test, silent rename, uncovered path
### Report             ← provenance: date, version, reporter, URL, severity
```

**Links are absolute permalinks on a SHA.** A relative target like `src/app/views.py#L35`
resolves against the issue's URL and is a 404; `blob/main/` works but moves with the next
refactor. Use the SHA you read the code at (`git rev-parse origin/<main>`):
`https://github.com/<owner>/<repo>/blob/<sha>/<path>#L340-L359`.

Do not paste the whole report — the compressed "Report" section is enough. Personal data of
the reporter only if the repo is private and the overlay allows it.

## 8 · File it and answer

Write the body to a file in the scratchpad and pass `--body-file`; `--body` with
backticks, quotes and diacritics is a pointless fight with the shell.

```bash
gh issue create --title '<Screen>: <defect>' --label bug --body-file <scratchpad>/issue.md
```

Title by **screen and defect**, not by feeling. Labels: `bug`, `chore` (cleanup),
`needs-spec`; never `in-progress` — the workflow derives it from a PR.

Answer the user with four things and nothing more: **number and link**, **cause in one
sentence**, **what you found beyond the report**, **what stays open**. State verdicts (b),
(c), (d) plainly — "this is not a bug but a missing feature" is worth more to the requester
than a filed issue.
