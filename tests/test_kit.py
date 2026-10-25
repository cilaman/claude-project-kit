"""Self-test of the kit: every profile combination renders into a repository that is green.

A template, a script and a skill agree on names only through CONVENTIONS.md, and nothing
but rendering them together shows whether they still do. The combinations span stacks on
purpose — the kit claims to be stack-agnostic, and only rendering it for several stacks
shows that no template still assumes one. Run:

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

try:  # Only the kit's own test uses it, to parse the rendered workflows.
    import yaml
except ImportError:  # pragma: no cover - reported, not skipped
    yaml = None

BASE = {
    "PROJECT_NAME": "Demo",
    "PROJECT_SLUG": "demo",
    "PROJECT_DESCRIPTION": "Demo is a test project.",
    "GITHUB_REPO": "me/demo",
    "MAIN_BRANCH": "main",
    "DOC_LANGUAGE": "English",
    "TODAY": "2026-10-25",
    "SRC_DIR": "src",
    "TOOLCHAIN": "none",
    "SETUP_COMMAND": "",
    "TEST_COMMAND": "make test",
    "LINT_COMMAND": "",
    "REGRESSION_COMMAND": "",
}

COMBINATIONS = (
    ([], {}),
    (
        ["requirements"],
        {"TOOLCHAIN": "node", "SETUP_COMMAND": "npm ci", "LINT_COMMAND": "npm run lint"},
    ),
    (
        ["ci-savings"],
        {
            "TOOLCHAIN": "go",
            "TEST_COMMAND": "go test ./...",
            "REGRESSION_COMMAND": "go test -tags regression ./...",
        },
    ),
    (["architecture"], {"TOOLCHAIN": "java", "TEST_COMMAND": "./gradlew test"}),
    (
        ["requirements", "ci-savings", "architecture"],
        {
            "TOOLCHAIN": "python",
            "SETUP_COMMAND": "uv sync --frozen",
            "TEST_COMMAND": "uv run pytest",
            "LINT_COMMAND": "uv run ruff check .",
            "REGRESSION_COMMAND": "uv run pytest -m regression",
        },
    ),
    (["architecture"], {"TOOLCHAIN": "other", "TEST_COMMAND": "mix test"}),
)


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def render(out, profiles, overrides=None):
    return scaffold.scaffold(out, ["core", *profiles], {**BASE, **(overrides or {})})


class RenderedRepositoryTests(unittest.TestCase):
    def test_every_combination_is_green_after_one_rebuild(self):
        for profiles, overrides in COMBINATIONS:
            label = f"{profiles} {overrides.get('TOOLCHAIN', 'none')}"
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                report = render(out, profiles, overrides)
                self.assertFalse(report["skipped"] or report["merge"], report)
                rebuild = run(
                    [sys.executable, "scripts/check_repo.py", "--rebuild-all", "--no-issues"], out
                )
                self.assertEqual(rebuild.returncode, 0, rebuild.stdout + rebuild.stderr)
                again = run([sys.executable, "scripts/check_repo.py", "--no-issues"], out)
                self.assertEqual(again.returncode, 0, again.stderr)
                self.assertNotIn(
                    "rewrote", again.stdout, "a second run must have nothing to rewrite"
                )
                tests = run(
                    [
                        sys.executable,
                        "-m",
                        "unittest",
                        "discover",
                        "-s",
                        "tests/scripts",
                        "-t",
                        ".",
                    ],
                    out,
                )
                self.assertEqual(tests.returncode, 0, tests.stderr[-3000:])
                if "architecture" in profiles:
                    arch = run([sys.executable, "scripts/check_architecture.py"], out)
                    self.assertEqual(arch.returncode, 0, arch.stderr)
                for path in out.rglob("*.py"):
                    compiled = run([sys.executable, "-m", "py_compile", str(path)], out)
                    self.assertEqual(compiled.returncode, 0, f"{path}: {compiled.stderr}")
                self.assertIsNotNone(yaml, "PyYAML is needed to check the rendered workflows")
                for path in (out / ".github").rglob("*.yml"):
                    yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_no_template_names_a_stack_outside_the_toolchain_action(self):
        """The stack enters through variables and one action — CONVENTIONS.md, Profiles."""
        stack_words = re.compile(
            r"\b(pytest|django|ruff|uv sync|npm|gradle|maven|cargo|dotnet)\b", re.I
        )
        allowed = {
            "core/.github/actions/setup-toolchain/action.yml",  # the one home of the presets
            "architecture/scripts/check_architecture.py",  # per-language import/skip presets
            "architecture/tests/scripts/test_check_architecture.py",  # examples of them
        }
        findings = []
        for path in sorted((KIT / "skills/project-init/templates").rglob("*")):
            rel = path.relative_to(KIT / "skills/project-init/templates").as_posix()
            if path.is_file() and rel not in allowed and not scaffold.CACHE_DIRS & set(path.parts):
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if stack_words.search(line):
                        findings.append(f"{rel}:{number}: {line.strip()}")
        self.assertEqual(findings, [])


class ConditionTests(unittest.TestCase):
    def test_variables_switch_files_and_blocks(self):
        with tempfile.TemporaryDirectory() as without, tempfile.TemporaryDirectory() as with_:
            render(Path(without), [])
            render(
                Path(with_),
                [],
                {
                    "TOOLCHAIN": "node",
                    "LINT_COMMAND": "npm run lint",
                    "REGRESSION_COMMAND": "npm run regression",
                },
            )
            self.assertFalse((Path(without) / ".github/workflows/regression.yml").exists())
            self.assertTrue((Path(with_) / ".github/workflows/regression.yml").exists())
            action = (Path(with_) / ".github/actions/setup-toolchain/action.yml").read_text()
            self.assertIn("actions/setup-node", action)
            self.assertNotIn("setup-python", action)
            self.assertNotIn("Lint", (Path(without) / ".github/workflows/ci.yml").read_text())
            self.assertIn("npm run lint", (Path(with_) / ".github/workflows/ci.yml").read_text())

    def test_other_toolchain_fails_loudly_until_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            render(Path(tmp), [], {"TOOLCHAIN": "other"})
            action = (Path(tmp) / ".github/actions/setup-toolchain/action.yml").read_text()
            self.assertIn("exit 1", action)

    def test_negation_markers_and_refusals(self):
        text = (
            "a\n<!-- kit:if requirements -->\nR\n<!-- kit:endif -->\n"
            "  # kit:if !var:X\n  N\n  # kit:endif\nz\n"
        )
        self.assertEqual(scaffold.render(text, {"core"}, {"X": ""}, "t"), "a\n  N\nz\n")
        self.assertEqual(
            scaffold.render(text, {"core", "requirements"}, {"X": "y"}, "t"), "a\nR\nz\n"
        )
        with self.assertRaises(scaffold.ScaffoldError):
            scaffold.render("{{" + "NOPE}}", set(), {}, "t")
        with self.assertRaises(scaffold.ScaffoldError):
            scaffold.render("# kit:if nope\nx\n# kit:endif\n", set(), {}, "t")
        with self.assertRaises(scaffold.ScaffoldError):
            scaffold.render("# kit:if TOOLCHAIN=go\nx\n# kit:endif\n", set(), {}, "t")


class ScaffoldTests(unittest.TestCase):
    def test_an_existing_file_is_kept_and_a_fragment_is_parked(self):
        with tempfile.TemporaryDirectory() as templates, tempfile.TemporaryDirectory() as tmp:
            core = Path(templates) / "core"
            core.mkdir()
            (core / "README.md").write_text("ours\n")
            (core / "settings.fragment.toml").write_text("[kit]\n")
            out = Path(tmp)
            (out / "README.md").write_text("theirs\n")
            (out / "settings.toml").write_text("[project]\n")
            original, scaffold.TEMPLATES = scaffold.TEMPLATES, Path(templates)
            try:
                report = scaffold.scaffold(out, ["core"], {})
            finally:
                scaffold.TEMPLATES = original
            self.assertEqual(report["skipped"], ["README.md"])
            self.assertEqual((out / "README.md").read_text(), "theirs\n")
            self.assertEqual((out / ".kit-merge/settings.toml").read_text(), "[kit]\n")
            self.assertEqual((out / "settings.toml").read_text(), "[project]\n")


class HookTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        render(self.root, [])
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
            self.payload(
                "Edit", file_path=str(self.index), old_string=header, new_string=header + " x"
            )
        )
        self.assertIn("--rebuild-backlog", reason or "")

    def test_an_edit_of_the_prose_passes(self):
        reason = guard_generated.verdict(
            self.payload(
                "Edit", file_path=str(self.index), old_string="# Backlog", new_string="# Backlog!"
            )
        )
        self.assertIsNone(reason)

    def test_the_register_is_refused_and_foreign_repos_pass(self):
        register = str(self.root / "backlog/tasks.tsv")
        self.assertIsNotNone(
            guard_generated.verdict(self.payload("Write", file_path=register, content=""))
        )
        with tempfile.TemporaryDirectory() as other:
            path = str(Path(other) / "backlog/tasks.tsv")
            self.assertIsNone(
                guard_generated.verdict(self.payload("Write", file_path=path, content=""))
            )


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
        named = re.findall(r"`([a-z-]+)`", conventions[conventions.index(line) :].split("\n\n")[0])
        for name in named:
            self.assertTrue((KIT / "skills" / name / "SKILL.md").exists(), name)

    def test_the_guard_references_named_by_the_skill_exist(self):
        skill = (KIT / "skills/guard/SKILL.md").read_text(encoding="utf-8")
        for rel in re.findall(r"`(references/[^`]+)`", skill):
            self.assertTrue((KIT / "skills/guard" / rel).exists(), rel)

    def test_manifests_are_valid_json(self):
        for rel in (
            ".claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            "hooks/hooks.json",
        ):
            json.loads((KIT / rel).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
