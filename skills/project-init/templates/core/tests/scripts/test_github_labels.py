"""Tests of scripts/github_labels.py — parsing the vocabulary and planning the sync."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import github_labels  # noqa: E402

SAMPLE = """\
# comment
labels:
  - name: bug
    color: d73a4a
    description: Defect — restores promised behaviour, commit is fix(…)
  - name: chore
    color: "FEF2C0"
    description: 'Cleanup: no change of behaviour'
"""


class ParseTest(unittest.TestCase):
    def test_reads_every_item(self):
        self.assertEqual(
            github_labels.parse_labels(SAMPLE),
            {
                "bug": ("d73a4a", "Defect — restores promised behaviour, commit is fix(…)"),
                "chore": ("fef2c0", "Cleanup: no change of behaviour"),
            },
        )

    def test_refuses_a_line_it_cannot_place(self):
        with self.assertRaises(ValueError):
            github_labels.parse_labels("labels:\n  - name: bug\n    colour: fff\n")

    def test_refuses_a_duplicate(self):
        text = "labels:\n  - name: a\n    color: fff\n  - name: a\n    color: 000\n"
        with self.assertRaises(ValueError):
            github_labels.parse_labels(text)

    def test_the_repository_file_parses(self):
        """The real vocabulary must stay in the shape the parser understands."""
        labels = github_labels.load_desired()
        for name in ("bug", "chore", "needs-spec", "in-progress", "nojira", "escaped-dod"):
            self.assertIn(name, labels)


class PlanTest(unittest.TestCase):
    def test_creates_aligns_and_deletes(self):
        desired = {"bug": ("d73a4a", "x"), "chore": ("fef2c0", "y")}
        current = {"bug": ("d73a4a", "old"), "enhancement": ("a2eeef", "")}
        actions = {(action, name) for action, name, _ in github_labels.plan(desired, current)}
        self.assertEqual(actions, {("apply", "bug"), ("apply", "chore"), ("delete", "enhancement")})

    def test_nothing_to_do(self):
        desired = {"bug": ("d73a4a", "x")}
        self.assertEqual(github_labels.plan(desired, dict(desired)), [])


if __name__ == "__main__":
    unittest.main()
