"""Tests of scripts/task_lifecycle.py — the decisions, without a network."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import task_lifecycle as lifecycle  # noqa: E402


def event(body="", action="opened", draft=False, merged=False, labels=(), author="octo"):
    return {
        "action": action,
        "pull_request": {
            "number": 7,
            "body": body,
            "draft": draft,
            "merged": merged,
            "user": {"login": author},
            "labels": [{"name": name} for name in labels],
        },
    }


def quiet(function, *args, **kwargs):
    """Runs `function` with stdout and stderr swallowed; returns its result."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return function(*args, **kwargs)


class ClosingNumbersTest(unittest.TestCase):
    def test_reads_every_closing_keyword(self):
        body = "Closes #12\nfixes #3\nResolved: #40"
        self.assertEqual(lifecycle.closing_numbers(body), [3, 12, 40])

    def test_ignores_html_comments(self):
        body = "<!-- write Closes #99 here -->\nCloses #5"
        self.assertEqual(lifecycle.closing_numbers(body), [5])

    def test_an_empty_template_closes_nothing(self):
        self.assertEqual(lifecycle.closing_numbers("Closes #\n"), [])
        self.assertEqual(lifecycle.closing_numbers(None), [])


class PlanTest(unittest.TestCase):
    def test_open_pr_puts_the_claim_on(self):
        actions = lifecycle.plan(event("Closes #4"))
        self.assertEqual(actions, ((4, "add-label", "in-progress"), (4, "add-assignee", "octo")))

    def test_merged_pr_keeps_the_assignee(self):
        actions = lifecycle.plan(event("Closes #4", action="closed", merged=True))
        self.assertEqual(actions, ((4, "remove-label", "in-progress"),))

    def test_abandoned_pr_clears_the_whole_claim(self):
        actions = lifecycle.plan(event("Closes #4", action="closed", merged=False))
        self.assertIn((4, "remove-assignee", "octo"), actions)
        self.assertIn((4, "remove-label", "in-progress"), actions)


class ApplyPlanTest(unittest.TestCase):
    def test_does_nothing_already_true(self):
        calls = []
        lines, failed = lifecycle.apply_plan(
            ((4, "add-label", "in-progress"),),
            state=lambda number: ({"in-progress"}, set()),
            run=calls.append,
        )
        self.assertEqual((calls, lines, failed), ([], [], False))

    def test_an_unreadable_issue_is_skipped_and_the_rest_runs(self):
        def state(number):
            if number == 1:
                raise lifecycle.LifecycleError("no such issue")
            return set(), set()

        calls = []
        lines, failed = lifecycle.apply_plan(
            ((1, "add-label", "in-progress"), (2, "add-label", "in-progress")),
            state=state,
            run=calls.append,
        )
        self.assertFalse(failed)
        self.assertEqual(len(calls), 1)
        self.assertIn("skipped", lines[0])

    def test_assignee_failure_does_not_fail_but_label_failure_does(self):
        def run(args):
            raise lifecycle.LifecycleError("refused")

        _, failed = lifecycle.apply_plan(
            ((1, "add-assignee", "bot"),), state=lambda n: (set(), set()), run=run
        )
        self.assertFalse(failed)
        _, failed = lifecycle.apply_plan(
            ((1, "add-label", "in-progress"),), state=lambda n: (set(), set()), run=run
        )
        self.assertTrue(failed)


class FilledBodyTest(unittest.TestCase):
    def test_fills_the_empty_template_line_in_place(self):
        body = "Closes #\n\n## What changes\n"
        self.assertEqual(lifecycle.filled_body(body, [9]), "Closes #9\n\n## What changes\n")

    def test_appends_when_there_is_no_empty_line(self):
        self.assertEqual(lifecycle.filled_body("text", [9, 10]), "text\n\nCloses #9\nCloses #10\n")

    def test_empty_body(self):
        self.assertEqual(lifecycle.filled_body("", [9]), "Closes #9\n")


class FinishedNumbersTest(unittest.TestCase):
    def test_only_files_that_arrived_count(self):
        files = [
            ("renamed", "backlog/done/BL-12-a.md"),
            ("added", "backlog/done/BL-13-b.md"),
            ("modified", "backlog/done/BL-14-c.md"),
            ("added", "backlog/BL-15-d.md"),
            ("removed", "backlog/done/BL-16-e.md"),
        ]
        self.assertEqual(lifecycle.finished_numbers(files), [12, 13])


class CheckTest(unittest.TestCase):
    def test_a_named_issue_passes(self):
        self.assertEqual(quiet(lifecycle.check, event("Closes #3"), files=()), 0)

    def test_nothing_named_nothing_derived_fails(self):
        self.assertEqual(quiet(lifecycle.check, event("Closes #"), files=()), 1)

    def test_derived_number_is_written_into_the_description(self):
        edits = []
        result = quiet(
            lifecycle.check,
            event("Closes #"),
            files=[("renamed", "backlog/done/BL-21-x.md")],
            edit=lambda number, body: edits.append(body),
        )
        self.assertEqual(result, 0)
        self.assertEqual(edits, ["Closes #21"])

    def test_nojira_alone_passes(self):
        self.assertEqual(quiet(lifecycle.check, event("", labels=["nojira"]), files=()), 0)

    def test_nojira_with_a_named_number_fails(self):
        self.assertEqual(quiet(lifecycle.check, event("Closes #3", labels=["nojira"]), files=()), 1)

    def test_nojira_with_a_derived_number_fails(self):
        result = quiet(
            lifecycle.check,
            event("", labels=["nojira"]),
            files=[("added", "backlog/done/BL-21-x.md")],
            edit=lambda number, body: None,
        )
        self.assertEqual(result, 1)


class FinishedTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "backlog" / "done").mkdir(parents=True)

    def tearDown(self):
        self.directory.cleanup()

    def test_a_draft_is_not_checked(self):
        (self.root / "backlog" / "BL-5-open.md").write_text("", encoding="utf-8")
        result = quiet(lifecycle.finished, event("Closes #5", draft=True), root=self.root)
        self.assertEqual(result, 0)

    def test_ready_pr_with_an_active_task_fails(self):
        (self.root / "backlog" / "BL-5-open.md").write_text("", encoding="utf-8")
        self.assertEqual(quiet(lifecycle.finished, event("Closes #5"), root=self.root), 1)

    def test_ready_pr_with_the_task_in_done_passes(self):
        (self.root / "backlog" / "done" / "BL-5-open.md").write_text("", encoding="utf-8")
        self.assertEqual(quiet(lifecycle.finished, event("Closes #5"), root=self.root), 0)

    def test_an_issue_without_a_file_passes(self):
        self.assertEqual(quiet(lifecycle.finished, event("Closes #6"), root=self.root), 0)


if __name__ == "__main__":
    unittest.main()
