#!/usr/bin/env python3
"""Derives from the diff how much of the test suite has something to say.

A change that touches nothing the tests read should not pay for the full test job.
Which change that is gets **computed from the diff**, never written by hand: a keyword
like `ONLY-DOC` in a commit or a PR can skip the tests on a change to the source too —
the one case where skipping is dangerous.

    git diff --name-only BASE HEAD | python3 scripts/ci_scope.py

The answer is one of three lanes, and it is deliberately pessimistic — anything short
of a proof lands in `full`, an empty or unreadable diff included. A guard wrong in the
other direction is a green build over untested code.

``none``
    Every changed path lies in `UNWATCHED`: nothing any test opens moved.
``fast``
    Every changed path lies in `FAST_LANE`. Tests **do** read those paths, but only the
    tests of the process scripts (`tests/scripts/`), so only those run — they are
    standard-library Python and take seconds, whatever the project's stack.
``full``
    Anything else.

**"Documentation" is not the dividing line.** Tests commonly read `docs/` and
`backlog/` (link checks, catalogues, generated indexes), so those paths are not
unwatched — the honest answer is to name their readers and run exactly those.
"""

import argparse
import os
import sys

# **The lists below are claims about the whole test suite**, not configuration. They
# are true on the day they are written and rot silently afterwards — the moment a test
# starts reading a path listed here, the lane skips a test that would have failed.
# `tests/scripts/test_ci_scope.py` keeps them honest; extend them only together with
# that guard, never instead of it.

#: Path prefixes no test opens, so a change confined to them cannot change what the
#: tests say. `scripts/check_repo.py` is a different question: its job never goes
#: through this filter, which is what keeps a documentation-only change checked at all.
UNWATCHED = (".claude/",)

#: Path prefixes read only by the tests of the process scripts. A diff confined to them
#: runs `tests/scripts/` and not the project's own suite. When a test of the project
#: starts reading one of them, the prefix leaves this list — it goes to the full lane.
FAST_LANE = (
    "backlog/",
    "docs/",
)

#: Where the fast lane's tests live; they are the only readers `FAST_LANE` may have.
FAST_LANE_TESTS = "tests/scripts/"


def tests_needed(paths):
    """Do the tests have anything to say about this diff?

    True unless every changed path lies in `UNWATCHED`. An empty list answers True on
    purpose: no paths means the diff could not be read, and a guard that reads "I know
    nothing" as "nothing to test" fails exactly when it is least noticed.
    """
    return bool(watched(paths)) or not [path for path in paths if path]


def watched(paths):
    """The changed paths the suite could read, ascending — the reason for the answer."""
    return sorted(path for path in paths if path and not path.startswith(UNWATCHED))


def lane(paths):
    """How much of the suite this diff needs: `none`, `fast` or `full`.

    `fast` has to be earned by every watched path at once — one path outside
    `FAST_LANE` and the whole diff pays full price. The `reasons` check is not a
    formality: `all()` over an empty list is True, so an unreadable diff would
    otherwise earn the fast lane by having no path to disqualify it.
    """
    if not tests_needed(paths):
        return "none"
    reasons = watched(paths)
    return "fast" if reasons and all(path.startswith(FAST_LANE) for path in reasons) else "full"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="write `tests_needed` and `lane` to $GITHUB_OUTPUT",
    )
    args = parser.parse_args(argv)

    paths = [row.strip() for row in sys.stdin.read().splitlines() if row.strip()]
    needed = tests_needed(paths)
    chosen = lane(paths)

    shown = []
    if not paths:
        print("the scope of the change could not be read — the full suite runs (safe side)")
    elif chosen == "none":
        shown = sorted(paths)
        print(f"no tests run — all {len(paths)} changed paths lie outside what they read:")
    elif chosen == "fast":
        shown = watched(paths)
        print(f"fast lane — {len(shown)} paths read only by {FAST_LANE_TESTS}; only those run:")
    else:
        shown = watched(paths)
        print(f"full suite — the change touches {len(shown)} paths the suite reads:")
    for path in shown[:10]:
        print(f"  {path}")
    if len(shown) > 10:
        print(f"  … and {len(shown) - 10} more")

    if args.github_output:
        target = os.environ.get("GITHUB_OUTPUT")
        if not target:
            print("$GITHUB_OUTPUT is missing — this belongs to a workflow step", file=sys.stderr)
            return 2
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"tests_needed={'true' if needed else 'false'}\n")
            handle.write(f"lane={chosen}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
