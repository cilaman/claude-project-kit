"""Every way a test can vanish from a run is a decision.

A skipped test is the one kind of failure that reports success: a run with sixty fewer
tests is as green as a run with all of them. So the inventory below lists every place
where a test may disappear, and each entry says **who answers the question instead**.
It is compared with the source both ways: an undeclared skip is a finding, and a
declared skip that no longer exists is a note about the past.

The inventory is **not** permission. The commonest bad skip is a condition that cannot
be false — `importorskip` of a dev dependency that is always installed, or a skip when
a file committed to the repository is missing. It reads as caution and behaves as noise.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"

#: What kind of answer the skip is waiting for. Small on purpose — a category per skip
#: would be a list of excuses, not a classification.
#:
#: * `commit`     — another environment of the same commit run answers it (CI has the
#:                  service, the checkout has the binary).
#: * `regression` — the environment that answers it is built by the regression workflow.
#: * `dormant`    — the set the test walks is empty **today**; it comes back into play
#:                  the moment somebody adds to it.
#: * `data`       — the committed sample does not carry the case.
CATEGORIES = {"commit", "regression", "dormant", "data"}

#: `"tests/path.py::function"` → `(category, who answers instead)`.
DECLARED_SKIPS: dict[str, tuple[str, str]] = {
    "tests/structure/test_layering.py::test_the_namespace_is_what_this_module_thinks_it_is": (
        "dormant",
        "comes into play with the first urls.py of the presentation module",
    ),
    "tests/structure/test_layering.py::test_a_domain_template_does_not_load_presentation_tags": (
        "dormant",
        "comes into play with the first template tag library of the presentation module",
    ),
}

#: The calls through which a test leaves the run.
SKIP_CALLS = {"skip", "skipif", "importorskip", "skipTest", "skipIf", "skipUnless"}


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return func.id if isinstance(func, ast.Name) else ""


def skips_in_source(source: str, name: str) -> set[str]:
    """`"path::function"` for every function containing or decorated by a skip.

    Module-level skips (`pytestmark`, a top-level `importorskip`) are reported under
    `path::<module>`, since they take the whole file out.
    """
    found = set()
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and _call_name(inner) in SKIP_CALLS:
                found.add(f"{name}::<module>")
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in [*node.decorator_list, *node.body]:
            if any(
                isinstance(call, ast.Call) and _call_name(call) in SKIP_CALLS
                for call in ast.walk(inner)
            ):
                found.add(f"{name}::{node.name}")
                break
    return found


def _actual_skips() -> set[str]:
    this = Path(__file__).resolve()
    found = set()
    for path in sorted(TESTS.rglob("*.py")):
        if path.resolve() == this:
            continue
        found |= skips_in_source(
            path.read_text(encoding="utf-8"), path.relative_to(ROOT).as_posix()
        )
    return found


def test_the_detector_finds_skips():
    """Anti-vacuum over a synthetic source."""
    source = (
        "import pytest\n"
        "@pytest.mark.skipif(True, reason='x')\n"
        "def test_a():\n    pass\n"
        "def test_b():\n    pytest.skip('no')\n"
        "def test_c():\n    assert True\n"
    )
    assert skips_in_source(source, "t.py") == {"t.py::test_a", "t.py::test_b"}


def test_every_skip_is_declared():
    undeclared = sorted(_actual_skips() - set(DECLARED_SKIPS))
    assert not undeclared, (
        "a test may leave the run without a declared reason — add it to DECLARED_SKIPS "
        f"with its category and who answers instead, or remove the skip: {undeclared}"
    )


def test_every_declaration_is_alive():
    stale = sorted(set(DECLARED_SKIPS) - _actual_skips())
    assert not stale, f"declared skips that no longer exist — delete the entries: {stale}"


def test_every_declaration_says_who_answers():
    bad = [
        key
        for key, (category, answer) in DECLARED_SKIPS.items()
        if category not in CATEGORIES or len(answer.split()) < 3
    ]
    assert not bad, f"unknown category or no answer: {bad}"
