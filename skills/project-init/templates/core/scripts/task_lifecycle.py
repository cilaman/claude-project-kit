"""Makes the issue queue follow the pull request instead of somebody's memory.

Three steps of the claim protocol (CLAUDE.md, the claim rule) would otherwise stand on
goodwill: the `in-progress` label, the assignee, and a `Closes #NN` that actually
carries a number. Goodwill drifts — closed issues keep the label for months and a PR
merged with an empty `Closes #` closes nothing.

    python3 scripts/task_lifecycle.py check     # the PR names its issues, derived if it can be
    python3 scripts/task_lifecycle.py finished  # a PR up for review has its task in done/
    python3 scripts/task_lifecycle.py sync      # label and assignee follow the pull request

All three read the pull-request event GitHub Actions leaves in `GITHUB_EVENT_PATH`;
`sync` and the derivation in `check` additionally need `gh` authenticated (`GH_TOKEN`).
Nothing here closes an issue — that stays native, through `Closes #NN` in the
description, because two paths to the same write are two places for it to drift.

The trigger hangs on the pull request, not on the branch name: a session whose branch
is dictated from outside (`claude/…`) would otherwise never be guarded.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

#: The claim as the queue reads it. The vocabulary lives in .github/labels.yml; this
#: is the one label with a mechanism behind it, not a second home of it.
IN_PROGRESS_LABEL = "in-progress"

#: The one way past the guard: this pull request claims no backlog item. A label and
#: not a keyword in the commit message — nothing reads commit messages, and a label
#: goes on and off without touching the branch.
NOJIRA_LABEL = "nojira"

#: The closing keywords GitHub honours, followed by `#NN`. Only the bare `#NN` form:
#: a cross-repository reference would close nothing here anyway.
CLOSING_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b[:\s]+#(\d+)", re.I)

#: HTML comments, multi-line included. Stripped first, so that a sentence *about*
#: closing an issue in the PR template is never read as an issue being closed.
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

#: The sync runs on a runner: an unreachable API must fail in seconds, not hold a slot.
GH_TIMEOUT_SECONDS = 30

ROOT = Path(__file__).resolve().parents[1]


class LifecycleError(RuntimeError):
    """The script cannot go on — no event, no `gh`, or a call GitHub refused."""


def closing_numbers(body):
    """Issue numbers the description closes, ascending.

    One reading for both the guard ("is there any?") and the sync ("which ones?") —
    two readings could let one pass while the other acts on nothing.
    """
    return sorted({int(number) for number in CLOSING_RE.findall(COMMENT_RE.sub(" ", body or ""))})


def pull_labels(pull):
    """Names of the labels the pull request carries right now."""
    return {(item or {}).get("name", "") for item in pull.get("labels") or ()}


def load_event(path=None):
    """The pull-request event as Actions left it on disk."""
    raw = path or os.environ.get("GITHUB_EVENT_PATH")
    if not raw:
        raise LifecycleError("GITHUB_EVENT_PATH is missing — this script belongs to a PR workflow")
    try:
        event = json.loads(Path(raw).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LifecycleError(f"the event could not be read ({error})") from error
    if "pull_request" not in event:
        raise LifecycleError("the event is not a pull request — no other trigger is served")
    return event


def plan(event):
    """What has to change on the issues, as `(number, kind, value)` triples.

    Pure on purpose: it is the whole decision and testable without a network.

    While the PR is open the claim is on — label and author. Once it is over the label
    comes off either way; the assignee stays on a merged PR (on a closed issue it is a
    record of who did the work) and comes off an abandoned one (whoever leaves a claim
    clears it).
    """
    pull = event["pull_request"]
    author = (pull.get("user") or {}).get("login", "")
    numbers = closing_numbers(pull.get("body", ""))
    if event.get("action") != "closed":
        actions = [(number, "add-label", IN_PROGRESS_LABEL) for number in numbers]
        if author:
            actions += [(number, "add-assignee", author) for number in numbers]
        return tuple(actions)
    actions = [(number, "remove-label", IN_PROGRESS_LABEL) for number in numbers]
    if not pull.get("merged") and author:
        actions += [(number, "remove-assignee", author) for number in numbers]
    return tuple(actions)


def _run(args):
    """One `gh` call; a non-zero exit is an error carrying what gh printed."""
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=GH_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError) as error:
        raise LifecycleError(f"`{' '.join(args)}` did not run ({error})") from error
    if done.returncode != 0:
        said = done.stderr.strip() or done.stdout.strip()
        raise LifecycleError(f"`{' '.join(args)}` failed: {said}")
    return done.stdout


def issue_state(number):
    """Labels and assignees the issue carries right now.

    Asked before every change so the sync is idempotent: `gh issue edit --remove-label`
    fails on a missing label, and a job red for having nothing to do teaches people to
    ignore it.
    """
    data = json.loads(_run(("gh", "issue", "view", str(number), "--json", "labels,assignees")))
    return (
        {item["name"] for item in data.get("labels", ())},
        {item["login"] for item in data.get("assignees", ())},
    )


def is_needed(kind, value, labels, assignees):
    """Would this change anything? Anything else is silence, not work."""
    held = labels if kind.endswith("label") else assignees
    return (value in held) if kind.startswith("remove") else (value not in held)


#: `gh issue edit` flag per kind of change.
EDIT_FLAG = {
    "add-label": "--add-label",
    "remove-label": "--remove-label",
    "add-assignee": "--add-assignee",
    "remove-assignee": "--remove-assignee",
}


def apply_plan(actions, state=issue_state, run=_run):
    """Carries the plan out; returns the lines to print and whether anything failed.

    Label failures fail the job, assignee failures are only said out loud: the label is
    the fact the queue is read by, whereas an account GitHub refuses to assign (a bot,
    somebody who left) would otherwise paint every PR red over a note about whom to ask.

    A number whose state cannot be read at all (an issue that does not exist, a number
    from before the series) is reported and skipped, and the rest of the plan still runs:
    a queue cleaned of what can be cleaned tells more truth than a red step.
    """
    lines, failed = [], False
    for number in sorted({number for number, _, _ in actions}):
        try:
            labels, assignees = state(number)
        except LifecycleError as error:
            lines.append(f"#{number}: state could not be read, skipped — {error}")
            continue
        for issue, kind, value in actions:
            if issue != number or not is_needed(kind, value, labels, assignees):
                continue
            try:
                run(("gh", "issue", "edit", str(number), EDIT_FLAG[kind], value))
            except LifecycleError as error:
                lines.append(f"#{number}: {kind} {value} failed — {error}")
                failed = failed or kind.endswith("label")
            else:
                lines.append(f"#{number}: {kind} {value}")
    return lines, failed


#: A task file where it lands when finished. `BL-NN` is the issue number, so a file
#: arriving here says which issue the PR closes — without anybody remembering it.
DONE_TASK_RE = re.compile(r"^backlog/done/BL-(\d+)-[^/]+\.md$")

#: Statuses GitHub reports for a path that has just arrived. A `modified` file in
#: `done/` is an old task somebody touched (a link, a typo) and must not link the PR to it.
ARRIVED = frozenset({"added", "renamed", "copied"})

#: The untouched `Closes #` of the PR template — filled in place, since the template
#: puts the reference first on purpose.
EMPTY_CLOSES_RE = re.compile(r"^[Cc]loses #[ \t]*$", re.M)

#: One line per changed file: status, tab, path.
PR_FILES_JQ = '.[] | "\\(.status)\\t\\(.filename)"'


def finished_numbers(files):
    """Numbers of the tasks this PR moves into `backlog/done/`, ascending."""
    return sorted(
        {
            int(found.group(1))
            for status, path in files
            if status in ARRIVED and (found := DONE_TASK_RE.match(path))
        }
    )


def pull_files(number):
    """Changed files of the pull request as `(status, path)`."""
    raw = _run(
        (
            "gh",
            "api",
            f"repos/{{owner}}/{{repo}}/pulls/{number}/files",
            "--paginate",
            "--jq",
            PR_FILES_JQ,
        )
    )
    return [tuple(row.split("\t", 1)) for row in raw.splitlines() if "\t" in row]


def filled_body(body, numbers):
    """The description with the missing `Closes #NN` lines written in."""
    lines = "\n".join(f"Closes #{number}" for number in numbers)
    if EMPTY_CLOSES_RE.search(body):
        return EMPTY_CLOSES_RE.sub(lambda _: lines, body, count=1)
    return f"{body.rstrip()}\n\n{lines}\n" if body.strip() else f"{lines}\n"


def _edit_body(number, body):
    _run(("gh", "pr", "edit", str(number), "--body", body))


def check(event, files=None, edit=_edit_body):
    """The description names every issue this PR closes — filled in when derivable.

    What is computable is not typed by hand: a task file arriving in `backlog/done/`
    names the issue, so the number is written into the description. The merge still
    does the closing — GitHub stays the only writer of the issue state.

    A bug or a cleanup without a spec file leaves no trace in the diff; there the
    description is the only source and the guard stays red until it is filled.

    `nojira` is the way out for a change too small for a backlog item. Label and number
    are mutually exclusive: a PR carrying both says it has no item while showing one.
    Whether the label went on rightly stays with review.
    """
    pull = event["pull_request"]
    body = pull.get("body") or ""
    named = closing_numbers(body)
    nojira = NOJIRA_LABEL in pull_labels(pull)
    if files is None and shutil.which("gh") is None:
        print("`gh` is not available — numbers were not derived from the diff, only read")
        files = ()
    derived = finished_numbers(pull_files(pull["number"]) if files is None else files)
    missing = [number for number in derived if number not in named]
    if nojira and (named or derived):
        print(
            f"the PR carries `{NOJIRA_LABEL}` but closes "
            + ", ".join(f"#{number}" for number in sorted(set(named + derived)))
            + " — the label says it has no backlog item. One or the other: remove "
            + f"`{NOJIRA_LABEL}`, or the number (and the task in done/)",
            file=sys.stderr,
        )
        return 1
    if missing:
        edit(pull["number"], filled_body(body, missing))
        print("filled in from the move to done/: " + ", ".join(f"#{n}" for n in missing))
    if not named and not missing:
        if nojira:
            print(
                f"the PR carries `{NOJIRA_LABEL}` — it claims no backlog item. It holds no "
                "claim either: if somebody else could work on this, it belongs to an issue"
            )
            return 0
        print(
            "the PR description names no issue and none can be derived from the diff — add "
            "`Closes #NN` with the item number (BL-NN is the issue number; without it the "
            f"merge closes nothing). A change needing no item passes with `{NOJIRA_LABEL}`",
            file=sys.stderr,
        )
        return 1
    print("the PR closes: " + ", ".join(f"#{n}" for n in sorted(set(named + missing))))
    return 0


def task_files(number, root=None):
    """`(active, finished)` paths of the task file for `BL-NN`; either may be empty.

    No file at all is a bug or a cleanup living as an issue alone — silence is right.
    """
    backlog = (root or ROOT) / "backlog"
    pattern = f"BL-{number}-*.md"
    return sorted(backlog.glob(pattern)), sorted((backlog / "done").glob(pattern))


def finished(event, root=None):
    """A PR offered for review has already moved its task into `done/`.

    The direction "task in done/ ⇒ issue closed" is unsatisfiable on a branch (the
    merge closes the issue), so `check_repo.py` checks it only on the main line. This
    is the direction that *is* satisfiable before the merge; without it the first task
    that skips the move turns the main line red after the merge instead of the PR red
    before it.

    Drafts are exempt: the protocol opens the draft at the very start, when nothing is
    finished, and a guard red for the whole life of every task gets ignored.
    """
    root = root or ROOT
    pull = event["pull_request"]
    if pull.get("draft"):
        print("the PR is a draft — task completion is not checked while work is in progress")
        return 0
    problems = []
    for number in closing_numbers(pull.get("body", "")):
        active, _ = task_files(number, root)
        problems += [
            f"{path.relative_to(root).as_posix()}: the PR is ready for review and closes "
            f"#{number}, but the task is not in backlog/done/ (the Definition of Done moves "
            "it in the branch; after the merge the main line would disagree with the queue)"
            for path in active
        ]
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("the tasks this PR closes are closed in the backlog too")
    return 0


def sync(event):
    """Puts the claim on while the PR lives and takes it off when it ends."""
    if shutil.which("gh") is None:
        raise LifecycleError("`gh` is not installed — the sync has nothing to write with")
    actions = plan(event)
    if not actions:
        print("the PR description names no issue — nothing to sync (the `check` step says so)")
        return 0
    lines, failed = apply_plan(actions)
    print("\n".join(lines) if lines else "the queue already agrees with the PR — nothing to do")
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("check", "finished", "sync"))
    parser.add_argument("--event", help="path to the event; GITHUB_EVENT_PATH otherwise")
    args = parser.parse_args(argv)
    try:
        return {"check": check, "finished": finished, "sync": sync}[args.command](
            load_event(args.event)
        )
    except LifecycleError as error:
        print(f"task_lifecycle: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
