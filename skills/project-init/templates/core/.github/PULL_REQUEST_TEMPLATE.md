Closes #

<!-- The issue number is the backlog item number (BL-NN), so the merge closes the issue
     through this line — natively, not through a CI step: two paths to the same write
     are two places for it to drift.
     The line carries three things: closing the issue, putting on the `in-progress` label
     and the assignee, and the green of the step "PR names its issue" in the job
     "Task lifecycle".
     **Moving a task file into `backlog/done/`? You do not have to write the number** —
     the workflow derives it from the move and fills it in. A bug or a cleanup without a
     spec file leaves no trace in the diff: write the number, or the PR stays red
     (editing the description is enough, no push needed).
     **A change too small for a backlog item passes with the `nojira` label** — leave the
     line empty then; the label and a number are mutually exclusive. It holds no claim:
     anything somebody else could also be doing belongs to an issue. -->

## What changes

<!-- Two sentences: why, not how. The how is in the diff. -->

## Verification

- [ ] `python3 scripts/check_repo.py`
<!-- kit:if python-django -->
- [ ] `{{LINT_COMMAND}}`
<!-- kit:endif -->
- [ ] `{{TEST_COMMAND}}`
- [ ] commits reference `— BL-NN`; backlog updated (status, `result_note:`, move to `done/`, regenerated)

<!-- The `in-progress` label, the assignee and the claim branch are not on this list on
     purpose: the workflow removes the label when the PR closes, GitHub deletes the
     branch after the merge. -->
