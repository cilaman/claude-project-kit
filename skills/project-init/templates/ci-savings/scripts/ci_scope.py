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
    Every changed path lies in `UNWATCHED`: nothing the suite opens moved.
``fast``
    Every changed path lies in `FAST_LANE`. The suite **does** read those paths, but
    only from the modules `FAST_LANE_TESTS` names, so only those run.
``full``
    Anything else.

**"Documentation" is not the dividing line.** Tests commonly read `docs/` and
`backlog/` (link checks, catalogues, generated indexes), so those paths are not
unwatched — the honest answer is to name their readers and run exactly those.
# kit:if python-django

The second question is **what the run measures**, and the diff does not answer it.
Coverage instrumentation is a large share of a run and a measuring instrument rather
than a test. It is keyed on the state of the pull request: a draft pays only for the
tests, a PR ready for review pays for the coverage measurement too. GitHub refuses to
merge a draft, so every merged change passes through a measured run.

    git diff --name-only BASE HEAD | python3 scripts/ci_scope.py --draft

`--draft` has to be **asserted**: a push, a missing flag or an event without a pull
request all measure.
# kit:endif
"""

import argparse
import os
import sys

# **The three lists below are claims about the whole test suite**, not configuration.
# They are true on the day they are written and rot silently afterwards — the moment a
# test starts reading a path listed here, the lane skips a test that would have failed.
# `tests/scripts/test_ci_scope.py` keeps them honest; extend the lists only together
# with that guard, never instead of it.

#: Path prefixes no test opens, so a change confined to them cannot change what the
#: tests say. `scripts/check_repo.py` is a different question: its job never goes
#: through this filter, which is what keeps a documentation-only change checked at all.
UNWATCHED = (".claude/",)

#: Path prefixes the suite reads, but only from the modules `FAST_LANE_TESTS` names in
#: full. A diff confined to them runs those modules and nothing else.
FAST_LANE = (
    "backlog/",
    "docs/",
)

#: Every test module that reads anything under `FAST_LANE`.
FAST_LANE_TESTS = ("tests/scripts/test_check_repo.py",)

# kit:if python-django
#: Serial and uninstrumented: a fraction of the suite would report a coverage collapse
#: that never happened, and building parallel workers costs more than a small subset
#: returns.
FAST_LANE_PYTEST_ARGS = ("-p", "no:xdist", "--no-cov", *FAST_LANE_TESTS)
# kit:endif


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


def measures_coverage(paths, draft=False):
    """Does this run write the coverage measurement?

    Only the full lane on a pull request that is not a draft: a fraction of the suite
    would report a coverage collapse that never happened, and a draft is bought once
    per iteration instead of once per merge candidate.
    """
# kit:if python-django
    return lane(paths) == "full" and not draft
# kit:endif
# kit:if !python-django
    return False  # this project measures no coverage in CI
# kit:endif


def pytest_args(paths, draft=False):
    """Arguments for the test command — empty means "everything, as configured".

    One place assembles them, so `--no-cov` is never spelled twice (once by the lane,
    once by the draft state) and the two can never disagree about which wins.
    """
# kit:if python-django
    if lane(paths) == "fast":
        return list(FAST_LANE_PYTEST_ARGS)
    return [] if measures_coverage(paths, draft) else ["--no-cov"]
# kit:endif
# kit:if !python-django
    return list(FAST_LANE_TESTS) if lane(paths) == "fast" else []
# kit:endif


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="write `tests_needed`, `lane`, `coverage` and `pytest_args` to $GITHUB_OUTPUT",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="the pull request is a draft — the run skips coverage measurement",
    )
    args = parser.parse_args(argv)

    paths = [row.strip() for row in sys.stdin.read().splitlines() if row.strip()]
    needed = tests_needed(paths)
    chosen = lane(paths)
    measured = measures_coverage(paths, args.draft)

    shown = []
    if not paths:
        print("the scope of the change could not be read — the full suite runs (safe side)")
    elif chosen == "none":
        shown = sorted(paths)
        print(f"no tests run — all {len(paths)} changed paths lie outside what they read:")
    elif chosen == "fast":
        shown = watched(paths)
        print(
            f"fast lane — the change touches only {len(shown)} paths read by "
            f"{len(FAST_LANE_TESTS)} modules; only those run:"
        )
    else:
        shown = watched(paths)
        print(f"full suite — the change touches {len(shown)} paths the suite reads:")
    for path in shown[:10]:
        print(f"  {path}")
    if len(shown) > 10:
        print(f"  … and {len(shown) - 10} more")
    # Said out loud: a run that measured nothing looks exactly like one that measured
    # everything and passed.
    if chosen != "none":
        print("coverage is measured" if measured else "coverage is not measured in this run")

    if args.github_output:
        target = os.environ.get("GITHUB_OUTPUT")
        if not target:
            print("$GITHUB_OUTPUT is missing — this belongs to a workflow step", file=sys.stderr)
            return 2
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"tests_needed={'true' if needed else 'false'}\n")
            handle.write(f"lane={chosen}\n")
            handle.write(f"coverage={'true' if measured else 'false'}\n")
            handle.write(f"pytest_args={' '.join(pytest_args(paths, args.draft))}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
