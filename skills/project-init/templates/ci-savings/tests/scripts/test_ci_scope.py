"""Tests of scripts/ci_scope.py — the lanes, and whether their lists still tell the truth.

The lane logic is easy; the lists are the risk. `UNWATCHED` and `FAST_LANE_TESTS` are
claims about the whole suite, so the second half of this module reads the suite and
fails the moment a test starts reading a path the lists say it does not.
"""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_scope  # noqa: E402

#: Names under which a test module refers to the real repository root.
ROOT_NAMES = {"ROOT", "REPO_ROOT", "BASE_DIR"}

THIS_MODULE = Path(__file__).resolve().relative_to(ROOT).as_posix()


class LaneTest(unittest.TestCase):
    def test_an_empty_diff_runs_everything(self):
        self.assertEqual(ci_scope.lane([]), "full")
        self.assertTrue(ci_scope.tests_needed([]))

    def test_only_unwatched_paths_run_nothing(self):
        self.assertEqual(ci_scope.lane([".claude/skills/x/SKILL.md"]), "none")

    def test_only_fast_lane_paths_run_the_fast_lane(self):
        self.assertEqual(ci_scope.lane(["docs/index.md", "backlog/BACKLOG.md"]), "fast")

    def test_unwatched_next_to_fast_lane_is_still_fast(self):
        self.assertEqual(ci_scope.lane([".claude/a.md", "docs/index.md"]), "fast")

    def test_one_source_path_makes_it_full(self):
        self.assertEqual(ci_scope.lane(["docs/index.md", "src/app.py"]), "full")

    def test_fast_lane_hands_over_exactly_its_readers(self):
        args = ci_scope.pytest_args(["docs/index.md"])
        for module in ci_scope.FAST_LANE_TESTS:
            self.assertIn(module, args)


def _real_root_reads(path):
    """First path segments a test module reads off the real repository root.

    **A textual heuristic, and its blind spots are part of the contract.** It sees
    `ROOT / "docs" / …` and `ROOT / "docs/x.md"` (any name in `ROOT_NAMES`), which is
    how the suite spells reads of the real tree. It does not see `Path("docs")`
    relative to the working directory, `ROOT.joinpath(...)` or a root under another
    name — spell reads as `ROOT / "…"` so this guard can see them. Fixtures that build
    their own tree in a temporary directory are rightly invisible to it.
    """
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Div)
            and isinstance(node.left, ast.Name)
            and node.left.id in ROOT_NAMES
            and isinstance(node.right, ast.Constant)
            and isinstance(node.right.value, str)
        ):
            found.add(node.right.value.strip("/").split("/")[0] + "/")
    return found


def _test_modules():
    return sorted(
        path
        for path in (ROOT / "tests").rglob("*.py")
        if path.relative_to(ROOT).as_posix() != THIS_MODULE
    )


class ListsAreHonestTest(unittest.TestCase):
    def test_there_are_test_modules_to_read(self):
        """Anti-vacuum: an empty walk would make both guards below pass on nothing."""
        self.assertTrue(_test_modules())

    def test_no_test_reads_an_unwatched_path(self):
        unwatched = {prefix.rstrip("/") + "/" for prefix in ci_scope.UNWATCHED}
        readers = [
            f"{path.relative_to(ROOT).as_posix()} reads {segment}"
            for path in _test_modules()
            for segment in _real_root_reads(path)
            if any(f"{segment}".startswith(prefix) for prefix in unwatched)
        ]
        self.assertEqual(readers, [], "a test reads a path ci_scope.UNWATCHED claims nobody reads")

    def test_every_reader_of_the_fast_lane_is_listed(self):
        listed = set(ci_scope.FAST_LANE_TESTS)
        unlisted = [
            f"{path.relative_to(ROOT).as_posix()} reads {segment}"
            for path in _test_modules()
            for segment in _real_root_reads(path)
            if segment.startswith(ci_scope.FAST_LANE)
            and path.relative_to(ROOT).as_posix() not in listed
        ]
        self.assertEqual(
            unlisted, [], "add the module to ci_scope.FAST_LANE_TESTS, or the fast lane skips it"
        )

    def test_every_listed_reader_exists(self):
        """A listed module that is gone would make the fast lane fail on a missing file."""
        missing = [name for name in ci_scope.FAST_LANE_TESTS if not (ROOT / name).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
