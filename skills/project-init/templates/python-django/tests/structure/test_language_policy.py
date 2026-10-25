"""Language guard — what the machine can check of "the code is written in English".

CLAUDE.md, the language rule: identifiers, file names, comments and docstrings are
English; user-facing text goes through i18n. A machine cannot tell English from
another language written without diacritics, so this guard checks the one
consequence it can: **every name the code defines, and every Python file name, is
ASCII.** A `def přepočítat()` or a `výpočet.py` fails here; a `def prepocitat()` does
not.

What it does **not** guard, said out loud so nobody mistakes the green for more: the
human language of ASCII identifiers, of comments and of docstrings. That stays with
review. Strings are not checked either — user-facing text legitimately lives there
(as i18n msgids).
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
#: Where code lives. Migrations are generated from the models and inherit their names.
ROOTS = (ROOT / "{{SRC_DIR}}", ROOT / "tests", ROOT / "scripts")


def _python_files():
    return sorted(
        path
        for root in ROOTS
        if root.is_dir()
        for path in root.rglob("*.py")
        if "migrations" not in path.parts
    )


def defined_names(source: str) -> list[tuple[int, str]]:
    """Every name the source defines: functions, classes, arguments, assignment targets,
    imports-as, loop and comprehension variables, exception aliases."""
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append((node.lineno, node.name))
        elif isinstance(node, ast.arg):
            names.append((node.lineno, node.arg))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append((node.lineno, node.id))
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            names.append((node.lineno, node.attr))
        elif isinstance(node, ast.alias) and node.asname:
            names.append((getattr(node, "lineno", 0), node.asname))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.append((node.lineno, node.name))
    return names


def test_there_is_code_to_read():
    """Anti-vacuum: an empty walk would make both guards pass on nothing."""
    assert _python_files()


def test_the_detector_finds_a_non_ascii_name():
    source = "def přepočet(částka):\n    výsledek = částka\n    return výsledek\n"
    offending = [name for _, name in defined_names(source) if not name.isascii()]
    assert offending == ["přepočet", "částka", "výsledek"], offending


def test_every_python_file_name_is_ascii():
    offending = [
        path.relative_to(ROOT).as_posix()
        for path in _python_files()
        if not path.relative_to(ROOT).as_posix().isascii()
    ]
    assert not offending, f"non-ASCII file or directory names: {offending}"


def test_every_defined_name_is_ascii():
    offending = [
        f"{path.relative_to(ROOT).as_posix()}:{line}: {name}"
        for path in _python_files()
        for line, name in defined_names(path.read_text(encoding="utf-8"))
        if not name.isascii()
    ]
    assert not offending, (
        "non-ASCII identifiers — code is written in English (CLAUDE.md, language rule): "
        + ", ".join(offending)
    )
