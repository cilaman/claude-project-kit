"""Tests of scripts/check_architecture.py — over repositories built in a temporary directory."""

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import check_architecture as arch  # noqa: E402

LAYERS = """
[[layers]]
name = "web"
paths = ["src/web/**"]
imports = ["web", "@app/web", "com.acme.web", "crate::web", "App\\\\Web"]
may_use = ["domain"]

[[layers]]
name = "domain"
paths = ["src/domain/**"]
imports = ["domain", "@app/domain", "com.acme.domain", "crate::domain", "App\\\\Domain"]
may_use = []
"""


class Repo:
    def __init__(self, root: Path, config: str):
        self.root = root
        self.write("architecture.toml", textwrap.dedent(config))

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")

    def problems(self):
        return arch.check(self.root)


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def repo(self, languages, extra=""):
        return Repo(Path(self._tmp.name), f"languages = {languages!r}\n" + LAYERS + extra)


class GlobTests(unittest.TestCase):
    def test_double_star_crosses_directories_and_single_does_not(self):
        self.assertTrue(arch.glob_regex("src/**").match("src/a/b.py"))
        self.assertTrue(arch.glob_regex("src/**/x.py").match("src/x.py"))
        self.assertFalse(arch.glob_regex("src/*.py").match("src/a/b.py"))


class LayerTests(RepoTestCase):
    """Each language preset is held to one forbidden and one allowed import."""

    CASES = {
        "python": ("py", "from web.views import page\n", "from domain.models import X\n"),
        "typescript": (
            "ts",
            "import { page } from '@app/web/page';\n",
            "import type { X } from '../domain/x';\n",
        ),
        "java": ("java", "import com.acme.web.Page;\n", "import com.acme.domain.X;\n"),
        "csharp": ("cs", "using com.acme.web;\n", "using com.acme.domain;\n"),
        "go": ("go", 'import (\n\t"fmt"\n\tw "web/pages"\n)\n', 'import "domain/x"\n'),
        "rust": ("rs", "use crate::web::page;\n", "use crate::domain::x;\n"),
        "php": ("php", "<?php\nuse App\\Web\\Page;\n", "<?php\nuse App\\Domain\\X;\n"),
    }

    def test_a_layer_must_not_import_a_layer_it_may_not_use(self):
        for language, (ext, upward, _) in self.CASES.items():
            with self.subTest(language=language):
                repo = self.repo([language])
                repo.write(f"src/web/page.{ext}", "\n")
                repo.write(f"src/domain/model.{ext}", upward)
                problems = repo.problems()
                self.assertTrue(any("layer `domain` imports" in p for p in problems), problems)

    def test_an_allowed_import_passes(self):
        for language, (ext, _, downward) in self.CASES.items():
            with self.subTest(language=language):
                repo = self.repo([language])
                repo.write(f"src/web/page.{ext}", downward)
                repo.write(f"src/domain/x.{ext}", "\n")
                self.assertEqual(repo.problems(), [])

    def test_a_relative_import_is_resolved_to_its_layer(self):
        repo = self.repo(["typescript"])
        repo.write("src/web/page.ts", "\n")
        repo.write("src/domain/x.ts", "import { page } from '../web/page';\n")
        self.assertTrue(any("imports `../web/page` of layer `web`" in p for p in repo.problems()))

    def test_a_string_in_go_code_is_not_an_import(self):
        repo = self.repo(["go"])
        repo.write("src/web/page.go", "\n")
        repo.write("src/domain/x.go", 'var s = []string{\n\t"web/pages",\n}\n')
        self.assertEqual(repo.problems(), [])

    def test_a_layer_matching_nothing_fails_unless_it_says_why(self):
        repo = self.repo(["python"])
        repo.write("src/web/page.py", "\n")
        self.assertTrue(any("`domain` matches no file" in p for p in repo.problems()))
        repo.write(
            "architecture.toml",
            (repo.root / "architecture.toml")
            .read_text()
            .replace("may_use = []", 'may_use = []\nempty = "no domain code yet"'),
        )
        self.assertEqual(repo.problems(), [])


FORBIDDEN = """
[[forbidden]]
name = "web-writes"
reason = "The database is written by a domain service only."
paths = ["src/web/**"]
pattern = '\\.save\\('
example = "form.save()"
"""


class ForbiddenTests(RepoTestCase):
    def test_a_forbidden_construct_is_found_and_an_exception_needs_a_live_reason(self):
        repo = self.repo(["python"], FORBIDDEN)
        repo.write("src/web/page.py", "form.save()\n")
        repo.write("src/domain/x.py", "\n")
        self.assertTrue(any("forbidden `web-writes`" in p for p in repo.problems()))
        allowed = (
            '\n[[forbidden.allowed]]\npath = "src/web/page.py"\nmatch = "form.save()"\n'
            'reason = "Legacy screen, moves to the service soon."\n'
        )
        repo.write("architecture.toml", (repo.root / "architecture.toml").read_text() + allowed)
        self.assertEqual(repo.problems(), [])
        repo.write("src/web/page.py", "\n")
        self.assertTrue(any("matches nothing" in p for p in repo.problems()))

    def test_a_pattern_that_misses_its_example_guards_nothing(self):
        repo = self.repo(
            ["python"], FORBIDDEN.replace('example = "form.save()"', 'example = "form.store()"')
        )
        repo.write("src/web/page.py", "\n")
        repo.write("src/domain/x.py", "\n")
        self.assertTrue(any("own `example`" in p for p in repo.problems()))


SKIPS = """
[skips]
paths = ["tests/**"]
"""


class SkipTests(RepoTestCase):
    def test_every_skip_is_declared_with_who_answers(self):
        repo = self.repo(["python", "javascript"], SKIPS)
        repo.write("src/web/page.py", "\n")
        repo.write("src/domain/x.py", "\n")
        repo.write("tests/test_a.py", "@pytest.mark.skip(reason='later')\ndef test_a(): ...\n")
        repo.write("tests/b.test.js", "it.skip('b', () => {})\n")
        problems = repo.problems()
        self.assertEqual(sum("undeclared skip" in p for p in problems), 2, problems)
        declared = textwrap.dedent("""
            [[skips.declared]]
            path = "tests/test_a.py"
            match = "mark.skip"
            category = "dormant"
            answers = "Nothing to walk until the first import lands."
        """)
        repo.write("architecture.toml", (repo.root / "architecture.toml").read_text() + declared)
        self.assertEqual(sum("undeclared skip" in p for p in repo.problems()), 1)


class AsciiAndVacuumTests(RepoTestCase):
    def test_a_non_ascii_file_name_is_reported(self):
        repo = Repo(Path(self._tmp.name), 'ascii_paths = ["src/**"]\n')
        repo.write("src/žiadosť.py", "\n")
        self.assertTrue(any("not ASCII" in p for p in repo.problems()))

    def test_a_configuration_without_rules_guards_nothing(self):
        repo = Repo(Path(self._tmp.name), "languages = []\n")
        self.assertTrue(any("declares no rule" in p for p in repo.problems()))


if __name__ == "__main__":
    unittest.main()
