"""Tests of scripts/check_repo.py — over small repositories built in a temporary directory.

The real backlog is never read here: what checks the real repository is the script
itself, in CI. These tests hold the script to the conventions it enforces.
"""

import sys
import tempfile
import textwrap
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import check_repo  # noqa: E402


def task_text(task_id, *, status="NEW", priority="P2", depends_on="—", extra="", title=None):
    lines = [
        "---",
        f"id: {task_id}",
        f"title: {title or 'Task ' + task_id}",
        f"priority: {priority}",
        f"status: {status}",
        "created: 2026-01-01",
    ]
    if check_repo.REQUIREMENTS_LAYER:
        lines.append("parent: —")
    lines += [f"depends_on: {depends_on}", "source: test"]
    lines += [line for line in extra.splitlines() if line]
    if check_repo.REQUIREMENTS_LAYER:
        lines.append("uc: —")
    return "\n".join(lines + ["---", "", "## Context", ""]) + "\n"


class Repo:
    """A minimal repository that passes every check once rebuilt."""

    def __init__(self, root: Path):
        self.root = root
        self.write("CLAUDE.md", "# rules\n")
        self.write("README.md", "# readme\n")
        layer = " [r](requirements.md) [u](use-cases.md)" if check_repo.REQUIREMENTS_LAYER else ""
        self.write(
            "docs/index.md",
            "# Map\n\n> **Status:** live · 2026-01-01\n\n"
            "[p](documentation-principles.md) [t](decisions/task-tracking.md)" + layer + "\n",
        )
        self.write(
            "docs/documentation-principles.md", "# P\n\n> **Status:** decided · 2026-01-01\n"
        )
        self.write("docs/decisions/task-tracking.md", "# T\n\n> **Status:** decided · 2026-01-01\n")
        self.write(
            "backlog/BACKLOG.md",
            "# Backlog\n\n<!-- generated: active-tasks -->\n<!-- /generated -->\n",
        )
        self.write(
            "backlog/DONE.md", "# Done\n\n<!-- generated: archive -->\n<!-- /generated -->\n"
        )
        self.write("backlog/tasks.tsv", "")
        self.write("backlog/_TEMPLATE.md", "template\n")
        self.write("backlog/done/.gitkeep", "")
        self.write("scripts/check_repo.py", "")
        self.write(".github/workflows/ci.yml", "")
        self.write(".github/workflows/task-lifecycle.yml", "")
        self.write(".github/ISSUE_TEMPLATE/bug.yml", "")
        self.write(".github/labels.yml", "")
        self.write(".github/PULL_REQUEST_TEMPLATE.md", "Closes #\n")
        if check_repo.REQUIREMENTS_LAYER:
            self.write(
                "docs/requirements.md",
                "# R\n\n> **Status:** live · 2026-01-01\n\n"
                "<!-- generated: requirements -->\n<!-- /generated -->\n",
            )
            self.write(
                "docs/requirements/_TEMPLATE.md", "# RQ\n\n> **Status:** live · YYYY-MM-DD\n"
            )
            self.write("docs/use-cases.md", CATALOGUE)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run(self, *argv):
        return check_repo.main([*argv, "--no-issues"], root=self.root, today=date(2026, 2, 1))

    def problems(self):
        return check_repo.check(self.root, with_issues=False)[0]


CATALOGUE = textwrap.dedent(
    """\
    # UC

    > **Status:** live · 2026-01-01

    ## A — Area

    | ID | Use case | Actor | Wave | State | Note |
    |---|---|---|---|---|---|
    | UC-01 | One | User | V0 | not started | |
    | UC-02 | Two | User | cancelled | not started | |

    <!-- generated: uc-backlog -->
    <!-- /generated -->
    """
)


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Repo(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()


class FrontMatterTests(unittest.TestCase):
    def test_comments_and_folded_scalars_are_read(self):
        data, problems = check_repo.front_matter(
            "---\nid: BL-1   # the id\nstatus_note: >\n  first line\n  second line\nuc: —\n---\n"
        )
        self.assertEqual(problems, [])
        self.assertEqual(data["id"], "BL-1")
        self.assertEqual(data["status_note"], "first line second line")
        self.assertEqual(list(data), ["id", "status_note", "uc"])

    def test_a_duplicated_key_is_reported(self):
        _, problems = check_repo.front_matter("---\nid: BL-1\nid: BL-2\n---\n")
        self.assertTrue(any("twice" in problem for problem in problems))


class TaskFileTests(RepoTestCase):
    def test_keys_out_of_order_are_reported(self):
        text = task_text("BL-3").replace("priority: P2\nstatus: NEW", "status: NEW\npriority: P2")
        self.repo.write("backlog/BL-3-x.md", text)
        self.assertTrue(any("out of order" in p for p in self.repo.problems()))

    def test_an_active_task_must_say_what_it_stands_on(self):
        self.repo.write("backlog/BL-3-x.md", task_text("BL-3").replace("depends_on: —\n", ""))
        self.assertTrue(any("depends_on" in p and "lacks" in p for p in self.repo.problems()))

    def test_a_closed_task_outside_done_is_reported(self):
        self.repo.write("backlog/BL-3-x.md", task_text("BL-3", status="DONE"))
        self.assertTrue(any("not in done/" in p for p in self.repo.problems()))

    def test_an_id_that_disagrees_with_the_file_name_is_reported(self):
        self.repo.write("backlog/BL-3-x.md", task_text("BL-4"))
        self.assertTrue(any("does not match the file name" in p for p in self.repo.problems()))


class IndexTests(RepoTestCase):
    def test_a_task_never_stands_above_what_it_stands_on(self):
        # Listed on purpose against the expected order: BL-2 is P1 but waits for BL-5.
        self.repo.write("backlog/BL-2-a.md", task_text("BL-2", priority="P1", depends_on="BL-5"))
        self.repo.write("backlog/BL-5-b.md", task_text("BL-5", priority="P3"))
        self.repo.write("backlog/BL-7-c.md", task_text("BL-7", priority="P1"))
        tasks, _ = check_repo.load_tasks(self.repo.root)
        ordered = [task.id for task in check_repo.order_active(tasks)[0]]
        self.assertEqual(ordered, ["BL-7", "BL-5", "BL-2"])

    def test_a_cycle_is_an_error(self):
        self.repo.write("backlog/BL-2-a.md", task_text("BL-2", depends_on="BL-5"))
        self.repo.write("backlog/BL-5-b.md", task_text("BL-5", depends_on="BL-2"))
        self.assertTrue(any("cycle" in p for p in self.repo.problems()))

    def test_a_hand_edit_of_the_generated_block_is_found(self):
        self.repo.write("backlog/BL-2-a.md", task_text("BL-2"))
        self.assertEqual(self.repo.run("--rebuild-all"), 0)
        index = self.repo.root / "backlog/BACKLOG.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace("NEW", "BLOCKED"), encoding="utf-8"
        )
        self.assertTrue(any("row of BL-2 differs" in p for p in self.repo.problems()))


class ArchiveTests(RepoTestCase):
    def test_a_closed_task_without_result_note_names_the_key(self):
        self.repo.write("backlog/done/BL-2-a.md", task_text("BL-2", status="DONE"))
        problems = self.repo.problems()
        self.assertTrue(any("result_note" in p for p in problems), problems)

    def test_rows_are_appended_newest_on_top_and_never_rewritten(self):
        self.repo.write(
            "backlog/done/BL-2-a.md", task_text("BL-2", status="DONE", extra="result_note: first")
        )
        self.assertEqual(self.repo.run("--rebuild-all"), 0)
        archive = self.repo.root / "backlog/DONE.md"
        first = archive.read_text(encoding="utf-8")
        self.repo.write(
            "backlog/done/BL-9-b.md", task_text("BL-9", status="DONE", extra="result_note: second")
        )
        self.assertEqual(self.repo.run("--rebuild-all"), 0)
        rows = [
            r for r in archive.read_text(encoding="utf-8").splitlines() if r.startswith("| BL-")
        ]
        self.assertEqual([r.split("|")[1].strip() for r in rows], ["BL-9", "BL-2"])
        self.assertIn(next(r for r in first.splitlines() if r.startswith("| BL-2")), rows)

    def test_an_orphan_row_is_reported(self):
        self.repo.write(
            "backlog/DONE.md",
            "<!-- generated: archive -->\n"
            "| BL-99 | [x](done/BL-99-x.md) | 2026 |\n"
            "<!-- /generated -->\n",
        )
        self.assertTrue(any("BL-99, which has no task file" in p for p in self.repo.problems()))


class LinkTests(RepoTestCase):
    def test_a_missing_target_is_reported_but_code_is_not_a_link(self):
        self.repo.write(
            "docs/index.md",
            self.repo.root.joinpath("docs/index.md").read_text() + "\n[x](gone.md)\n",
        )
        self.repo.write("README.md", "# r\n\n```\n[example](nowhere.md)\n```\n")
        problems = self.repo.problems()
        self.assertTrue(any("gone.md" in p for p in problems))
        self.assertFalse(any("nowhere.md" in p for p in problems))

    def test_moving_a_task_to_done_is_repaired(self):
        self.repo.write("backlog/BL-2-a.md", task_text("BL-2") + "\n[map](../docs/index.md)\n")
        self.repo.write(
            "docs/notes.md", "# N\n\n> **Status:** live · 2026-01-01\n\n[t](../backlog/BL-2-a.md)\n"
        )
        self.repo.write(
            "docs/index.md",
            self.repo.root.joinpath("docs/index.md").read_text() + "[n](notes.md)\n",
        )
        moved = self.repo.root / "backlog/done/BL-2-a.md"
        text = (self.repo.root / "backlog/BL-2-a.md").read_text(encoding="utf-8")
        moved.write_text(
            text.replace("status: NEW", "status: DONE").replace(
                "source: test", "source: test\nresult_note: done"
            ),
            encoding="utf-8",
        )
        (self.repo.root / "backlog/BL-2-a.md").unlink()
        self.assertEqual(self.repo.run("--rebuild-all"), 0, self.repo.problems())
        self.assertIn("](../../docs/index.md)", moved.read_text(encoding="utf-8"))
        self.assertIn(
            "](../backlog/done/BL-2-a.md)", (self.repo.root / "docs/notes.md").read_text()
        )


class DocumentTests(RepoTestCase):
    def test_a_document_outside_the_map_is_reported(self):
        self.repo.write("docs/lost.md", "# L\n\n> **Status:** live · 2026-01-01\n")
        self.assertTrue(any("lost.md: not linked" in p for p in self.repo.problems()))

    def test_a_document_without_header_is_reported(self):
        self.repo.write("docs/bare.md", "# B\n")
        self.assertTrue(any("bare.md: header block" in p for p in self.repo.problems()))

    def test_a_leftover_placeholder_is_reported(self):
        self.repo.write("README.md", "# " + "{{" + "PROJECT_NAME" + "}}\n")
        self.assertTrue(any("left over from init" in p for p in self.repo.problems()))


class RequirementLayerTests(RepoTestCase):
    def setUp(self):
        self._layer = check_repo.REQUIREMENTS_LAYER
        check_repo.REQUIREMENTS_LAYER = True
        super().setUp()

    def tearDown(self):
        super().tearDown()
        check_repo.REQUIREMENTS_LAYER = self._layer

    def _task(self, task_id, status, parent="—", uc="—", folder="backlog"):
        text = task_text(
            task_id, status=status, extra="result_note: ok" if status == "DONE" else ""
        )
        text = text.replace("parent: —", f"parent: {parent}").replace("uc: —", f"uc: {uc}")
        self.repo.write(f"{folder}/{task_id}-x.md", text)

    def test_states_are_derived_from_the_claiming_tasks(self):
        self.repo.write(
            "docs/requirements/RQ-01-a.md", "# Need A\n\n> **Status:** live · 2026-01-01\n"
        )
        self._task("BL-2", "DONE", parent="RQ-01", uc="UC-01", folder="backlog/done")
        self._task("BL-3", "IN_PROGRESS", parent="RQ-01", uc="UC-01")
        self.assertEqual(self.repo.run("--rebuild-all"), 0, self.repo.problems())
        requirements = (self.repo.root / "docs/requirements.md").read_text(encoding="utf-8")
        self.assertIn("| Need A | in progress | 1/2 |", requirements)
        catalogue = (self.repo.root / "docs/use-cases.md").read_text(encoding="utf-8")
        self.assertIn("| UC-01 | One | User | V0 | in progress |", catalogue)
        self.assertIn("| UC-02 | Two | User | cancelled | cancelled |", catalogue)

    def test_unknown_parent_and_use_case_are_errors(self):
        self._task("BL-2", "NEW", parent="RQ-07", uc="UC-42")
        problems = self.repo.problems()
        self.assertTrue(any("RQ-07" in p for p in problems))
        self.assertTrue(any("UC-42" in p for p in problems))

    def test_a_done_task_must_not_claim_a_cancelled_case(self):
        self._task("BL-2", "DONE", uc="UC-02", folder="backlog/done")
        self.assertTrue(any("cancelled UC-02" in p for p in self.repo.problems()))


class EndToEndTests(RepoTestCase):
    def test_a_fresh_repository_is_green_after_one_rebuild(self):
        self.repo.write("backlog/BL-2-a.md", task_text("BL-2", extra="status_note: >\n  waiting"))
        self.assertEqual(self.repo.run("--rebuild-all"), 0, self.repo.problems())
        self.assertEqual(self.repo.problems(), [])
        register = (self.repo.root / "backlog/tasks.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(register[0].split("\t"), list(check_repo.REGISTER_COLUMNS))
        self.assertTrue(register[1].startswith("BL-2\tP2\tNEW\t"))


if __name__ == "__main__":
    unittest.main()
