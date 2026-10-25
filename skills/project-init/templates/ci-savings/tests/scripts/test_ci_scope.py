"""Tests of scripts/ci_scope.py — the lanes, and whether their lists still tell the truth.

The lane logic is easy; the lists are the risk. `UNWATCHED` and `FAST_LANE` are claims
about the whole suite, so the second half of this module reads every test file of the
project, in whatever language, and fails the moment one starts naming a path the lists
say it does not read.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_scope  # noqa: E402

THIS_MODULE = Path(__file__).resolve().relative_to(ROOT).as_posix()

#: What a test file looks like, in the common ecosystems. Extend it when the project
#: keeps tests elsewhere — a test this list misses is a reader the guard cannot see.
TEST_FILE_PATTERNS = (
    r"(^|/)tests?/",
    r"(^|/)__tests__/",
    r"(^|/)src/test/",
    r"\.(test|spec)\.[cm]?[jt]sx?$",
    r"_test\.(go|py|rb|exs?)$",
    r"(^|/)test_[^/]+\.py$",
    r"Tests?\.(java|kt|cs|php)$",
    r"_spec\.rb$",
)
SKIPPED_DIRS = {".git", "node_modules", ".venv", "venv", "vendor", "target", "build", "dist"}
TEXT_SUFFIXES = {
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java", ".kt", ".kts", ".cs",
    ".go", ".rs", ".php", ".rb", ".ex", ".exs", ".swift", ".scala", ".sh", ".json", ".yml",
    ".yaml", ".toml",
}  # fmt: skip


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


def mentions(text, prefix):
    """Does the text name the path as a string literal — `"docs"`, `'docs/x.md'`, …?

    **A textual heuristic, and its blind spots are part of the contract.** It sees a
    quoted literal starting with the prefix, which is how a test in any language names
    a path of the real tree. It does not see a path assembled from pieces. Its false
    positives fall on the safe side: they push a prefix to the full lane.
    """
    name = re.escape(prefix.strip("/"))
    return re.search(rf"""["'`](?:\./)?{name}(?:/[^"'`]*)?["'`]""", text) is not None


def test_files():
    found = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if SKIPPED_DIRS & set(path.parts) or not path.is_file() or rel == THIS_MODULE:
            continue
        if path.suffix in TEXT_SUFFIXES and any(re.search(p, rel) for p in TEST_FILE_PATTERNS):
            found.append((rel, path.read_text(encoding="utf-8", errors="replace")))
    return sorted(found)


class ListsAreHonestTest(unittest.TestCase):
    def test_there_are_test_files_to_read(self):
        """Anti-vacuum: an empty walk would make both guards below pass on nothing."""
        self.assertTrue(any(rel.startswith(ci_scope.FAST_LANE_TESTS) for rel, _ in test_files()))

    def test_the_heuristic_sees_the_usual_spellings(self):
        self.assertTrue(mentions('ROOT / "docs" / "index.md"', "docs/"))
        self.assertTrue(mentions("readFileSync('./docs/index.md')", "docs/"))
        self.assertFalse(mentions('"documents"', "docs/"))

    def test_no_test_reads_an_unwatched_path(self):
        readers = [
            f"{rel} names {prefix}"
            for rel, text in test_files()
            for prefix in ci_scope.UNWATCHED
            if mentions(text, prefix)
        ]
        self.assertEqual(readers, [], "a test reads a path ci_scope.UNWATCHED claims nobody reads")

    def test_only_process_script_tests_read_the_fast_lane(self):
        readers = [
            f"{rel} names {prefix}"
            for rel, text in test_files()
            if not rel.startswith(ci_scope.FAST_LANE_TESTS)
            for prefix in ci_scope.FAST_LANE
            if mentions(text, prefix)
        ]
        self.assertEqual(
            readers, [], "the fast lane runs only tests/scripts/ — move the prefix out of FAST_LANE"
        )


if __name__ == "__main__":
    unittest.main()
