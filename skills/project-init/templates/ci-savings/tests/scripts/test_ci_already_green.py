"""Tests of scripts/ci_already_green.py that need no network."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_already_green  # noqa: E402


class JobNameTest(unittest.TestCase):
    def test_job_name_is_the_display_name_of_the_test_job(self):
        """The API reports display names; a rename would make every answer "not green"."""
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        block = re.search(r"^  app-test:\n((?:    .*\n|\n)+)", workflow, re.M)
        self.assertIsNotNone(block, "ci.yml has no job `app-test`")
        name = re.search(r"^    name:\s*(.+?)\s*$", block.group(1), re.M)
        self.assertIsNotNone(name, "job `app-test` has no display name")
        self.assertEqual(name.group(1).strip("\"'"), ci_already_green.JOB_NAME)


class PessimismTest(unittest.TestCase):
    def test_an_unknown_commit_has_no_candidates(self):
        self.assertEqual(ci_already_green.matching_candidates("0" * 40), [])

    def test_no_repo_means_not_green(self):
        self.assertIsNone(ci_already_green.already_green("0" * 40, ""))


if __name__ == "__main__":
    unittest.main()
