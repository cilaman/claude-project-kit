"""Has this exact tree already been proven green by a run of the test job?

A merge tests again the tree a pull request has just tested. Typically about half of
the pushes to the main line carry a tree identical to some pull request head — a full
test run for an answer somebody already bought. Direct pushes have no such twin and
run; that is the point, not a gap.

    python3 scripts/ci_already_green.py --sha "$GITHUB_SHA" --github-output

**The tree, not the commit.** Merge, rebase and squash each make a new commit with a
new sha; what survives is the content. `git rev-parse <sha>^{tree}` fingerprints it,
so two histories with the same result hand the answer to each other.

**Pessimistic, harder than `ci_scope.py`.** A `yes` has to be evidenced: a candidate
with an identical tree whose `Tests` job the API confirms concluded `success`. Anything
else — no `gh`, a network error, an unknown tree, a run that was not green — answers
`no`, meaning run them. A false green on the main line is the one mistake this filter
must not make; a wasted run is the price it happily pays for that.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

#: The display name of job `app-test` in `.github/workflows/ci.yml`, not its key — the
#: check-runs API reports names. `tests/scripts/test_ci_already_green.py` holds the two
#: together, so a rename cannot quietly turn every answer into "not green".
JOB_NAME = "Tests"

#: An unreachable network costs seconds and then the answer is "test it".
GH_TIMEOUT_SECONDS = 15

#: Where candidates come from besides the parents: the pull-request heads cover rebase
#: and squash merges, where the tested commit is an ancestor of nothing. The workflow
#: fetches them; without that fetch this source is empty and the answer is "test it".
PULL_HEAD_REFS = "refs/remotes/pr/"


def git(*args):
    """Output of a git command, or `None` when it failed — never an exception."""
    try:
        finished = subprocess.run(
            ("git", *args), capture_output=True, text=True, timeout=GH_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return finished.stdout.strip() if finished.returncode == 0 else None


def tree_of(commit):
    """The tree a commit points at, or `None` when git does not know the commit."""
    return git("rev-parse", f"{commit}^{{tree}}")


def candidates(sha):
    """Commits that could carry the green for `sha`, without `sha` itself.

    Parents first — a merge commit's second parent is the cheapest, surest answer.
    """
    found = (git("rev-parse", f"{sha}^@") or "").split()
    found += (git("for-each-ref", "--format=%(objectname)", PULL_HEAD_REFS) or "").split()
    seen = set()
    return [c for c in found if c != sha and not (c in seen or seen.add(c))]


def matching_candidates(sha):
    """Candidates whose tree is identical to the tree of `sha`."""
    wanted = tree_of(sha)
    if not wanted:
        return []
    return [c for c in candidates(sha) if tree_of(c) == wanted]


def job_succeeded(repo, commit):
    """Did `JOB_NAME` conclude `success` for this commit?

    Every failure mode answers False — that is the whole safety argument. A re-run
    lists the job more than once, so any one success is enough.
    """
    if shutil.which("gh") is None:
        return False
    try:
        finished = subprocess.run(
            ("gh", "api", f"repos/{repo}/commits/{commit}/check-runs", "--paginate"),
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if finished.returncode != 0:
        return False
    try:
        payload = json.loads(finished.stdout or "{}")
    except json.JSONDecodeError:
        return False
    return any(
        run.get("name") == JOB_NAME and run.get("conclusion") == "success"
        for run in payload.get("check_runs", [])
    )


def already_green(sha, repo):
    """The commit that already proved this tree, or `None`."""
    for candidate in matching_candidates(sha):
        if job_succeeded(repo, candidate):
            return candidate
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sha", required=True, help="the commit being asked about")
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help="`owner/repo`; $GITHUB_REPOSITORY by default",
    )
    parser.add_argument(
        "--github-output", action="store_true", help="write `already_green` to $GITHUB_OUTPUT"
    )
    args = parser.parse_args(argv)

    proven_by = already_green(args.sha, args.repo) if args.repo else None
    if proven_by:
        print(f"tree {tree_of(args.sha)} already has a green run — commit {proven_by}, skipping")
    elif not args.repo:
        print("$GITHUB_REPOSITORY is missing — tests run (safe side)")
    else:
        print(f"tree {tree_of(args.sha) or '?'} has no green run — tests run")

    if args.github_output:
        target = os.environ.get("GITHUB_OUTPUT")
        if not target:
            print("$GITHUB_OUTPUT is missing — this belongs to a workflow step", file=sys.stderr)
            return 2
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"already_green={'true' if proven_by else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
