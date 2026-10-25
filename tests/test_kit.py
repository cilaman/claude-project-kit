"""Self-test of the kit: every profile combination renders into a repository that is green.

A template, a script and a skill agree on names only through CONVENTIONS.md, and nothing
but rendering them together shows whether they still do. Run:

    python3 -m unittest discover -s tests -t .
"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "skills/project-init"))
sys.path.insert(0, str(KIT / "hooks"))

import guard_generated  # noqa: E402
import scaffold  # noqa: E402

VARIABLES = {
    "PROJECT_NAME": "Demo",
    "PROJECT_SLUG": "demo",
    "PROJECT_DESCRIPTION": "Demo is a test project.",
    "GITHUB_REPO": "me/demo",
    "MAIN_BRANCH": "main",
    "DOC_LANGUAGE": "English",
    "TODAY": "2026-10-25",
    "PYTHON_VERSION": "3.12",
    "SRC_DIR": "src",
    "TEST_COMMAND": "uv run pytest",
    "LINT_COMMAND": "uv run ruff check src tests scripts",
    "PRESENTATION_MODULE": "web",
    "DJANGO_PROJECT": "demo",
}

COMBINATIONS = (
    ([], []),
    (["requirements"], []),
    (["ci-savings"], []),
    (["python-django"], []),
    (["requirements", "ci-savings", "python-django"], ["tenancy"]),
)


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


class RenderedRepositoryTests(unittest.TestCase):
    def test_every_combination_is_green_after_one_rebuild(self):
        for profiles, options in COMBINATIONS:
            with self.subTest(profiles=profiles, options=options), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                report = scaffold.scaffold(out, ["core", *profiles], options, VARIABLES)
                self.assertFalse(report["skipped"] or report["merge"], report)
                rebuild = run([sys.executable, "scripts/check_repo.py", "--rebuild-all", "--no-issues"], out)
                self.assertEqual(rebuild.returncode, 0, rebuild.stdout + rebuild.stderr)
                again = run([sys.executable, "scripts/check_repo.py", "--no-issues"], out)
                self.assertEqual(again.returncode, 0, again.stderr)
                self.assertNotIn("rewrote", again.stdout, "a second run must have nothing to rewrite")
                tests = run([sys.executable, "-m", "unittest", "discover", "-s", "tests/scripts", "-t", "."], out)
                self.assertEqual(tests.returncode, 0, tests.stderr[-3000:])
                for path in out.rglob("*.py"):
                    compiled = run([sys.executable, "-m", "py_compile", str(path)], out)
                    self.assertEqual(compiled.returncode, 0, f"{path}: {compiled.stderr}")

    def test_tenancy_files_exist_only_with_tenancy(self):
        with tempfile.TemporaryDirectory() as with_, tempfile.TemporaryDirectory() as without:
            scaffold.scaffold(Path(with_), ["core", "python-django"], ["tenancy"], VARIABLES)
            scaffold.scaffold(Path(without), ["core", "python-django"], [], VARIABLES)
            self.assertTrue((Path(with_) / "tests/tenancy/test_rls_policies.py").exists())
            self.assertFalse((Path(without) / "tests/tenancy").exists())
            self.assertNotIn("Tenant isolation", (Path(without) / "CLAUDE.md").read_text())


class ScaffoldTests(unittest.TestCase):
    def test_conditions_negation_and_markers(self):
        text = "a\n<!-- kit:if requirements -->\nR\n<!-- kit:endif -->\n  # kit:if !requirements\n  N\n  # kit:endif\nz\n"
        self.assertEqual(scaffold.render(text, {"core"}, {}, "t"), "a\n  N\nz\n")
        self.assertEqual(scaffold.render(text, {"core", "requirements"}, {}, "t"), "a\nR\nz\n")

    def test_an_unknown_placeholder_or_condition_refuses(self):
        with self.assertRaises(scaffold.ScaffoldError):
            scaffold.render("{{" + "NOPE}}", set(), {}, "t")
        with self.assertRaises(scaffold.ScaffoldError):
            scaffold.render("# kit:if nope\nx\n# kit:endif\n", set(), {}, "t")

    def test_an_existing_file_is_kept_and_a_fragment_is_parked(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "README.md").write_text("theirs\n")
            (out / "pyproject.toml").write_text("[project]\nname = 'x'\n")
            report = scaffold.scaffold(out, ["core", "python-django"], [], VARIABLES)
            self.assertIn("README.md", report["skipped"])
            self.assertEqual((out / "README.md").read_text(), "theirs\n")
            self.assertTrue((out / ".kit-merge/pyproject.toml").exists())
            self.assertEqual((out / "pyproject.toml").read_text(), "[project]\nname = 'x'\n")


class HookTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        scaffold.scaffold(self.root, ["core"], [], VARIABLES)
        run([sys.executable, "scripts/check_repo.py", "--rebuild-all", "--no-issues"], self.root)
        self.index = self.root / "backlog/BACKLOG.md"

    def tearDown(self):
        self._tmp.cleanup()

    def payload(self, tool, **data):
        return {"tool_name": tool, "tool_input": data, "cwd": str(self.root)}

    def test_an_edit_inside_a_generated_block_is_refused(self):
        text = self.index.read_text()
        header = next(line for line in text.splitlines() if line.startswith("| ID"))
        reason = guard_generated.verdict(
            self.payload("Edit", file_path=str(self.index), old_string=header, new_string=header + " x")
        )
        self.assertIn("--rebuild-backlog", reason or "")

    def test_an_edit_of_the_prose_passes(self):
        reason = guard_generated.verdict(
            self.payload("Edit", file_path=str(self.index), old_string="# Backlog", new_string="# Backlog!")
        )
        self.assertIsNone(reason)

    def test_the_register_is_refused_and_foreign_repos_pass(self):
        register = str(self.root / "backlog/tasks.tsv")
        self.assertIsNotNone(guard_generated.verdict(self.payload("Write", file_path=register, content="")))
        with tempfile.TemporaryDirectory() as other:
            path = str(Path(other) / "backlog/tasks.tsv")
            self.assertIsNone(guard_generated.verdict(self.payload("Write", file_path=path, content="")))


class SkillManifestTests(unittest.TestCase):
    def test_every_skill_names_itself_and_says_when_to_use_it(self):
        skills = sorted((KIT / "skills").glob("*/SKILL.md"))
        self.assertGreaterEqual(len(skills), 7)
        for path in skills:
            front = path.read_text(encoding="utf-8").split("---")[1]
            self.assertIn(f"name: {path.parent.name}\n", front, path)
            self.assertRegex(front, r"description: .{80,}", path)

    def test_the_overlay_list_of_conventions_names_real_skills(self):
        conventions = (KIT / "skills/project-init/CONVENTIONS.md").read_text(encoding="utf-8")
        line = next(row for row in conventions.splitlines() if "extends the plugin skill" in row)
        named = re.findall(r"`([a-z-]+)`", conventions[conventions.index(line):].split("\n\n")[0])
        for name in named:
            self.assertTrue((KIT / "skills" / name / "SKILL.md").exists(), name)

    def test_manifests_are_valid_json(self):
        for rel in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "hooks/hooks.json"):
            json.loads((KIT / rel).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
