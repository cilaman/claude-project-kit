"""Write guard — the presentation validates, a domain service writes.

`web/` validates a form and hands `cleaned_data` on; it must not
write through the ORM itself. A write path living in a view cannot be called without
a request, so a future `api/`, a management command or a queue would have to write it
again — and with it the audit record and the checks the service carries.

The test reads the AST: a violation is caught in code no test ever calls. It does
**not** look at the type of the model — what is forbidden is the write in the
presentation, whatever it writes.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRESENTATION = ROOT / "src" / "web"

#: Methods that write on whatever they are called: a model, a queryset, a ModelForm.
WRITE_METHODS = {"save", "delete"}

#: Methods that write only behind a manager — `update` alone is a dict method.
MANAGER_WRITE_METHODS = {
    "create",
    "update",
    "bulk_create",
    "bulk_update",
    "get_or_create",
    "update_or_create",
}

#: Receivers that make the methods above a database write.
MANAGERS = {"objects", "_default_manager", "_base_manager"}

#: Writes that legitimately stay in the presentation, each with its reason — a silent
#: exception is exactly the drift this guard exists to stop. Key: `("path:line",
#: "expression")` as the failure message prints it; value: the reason (5+ words).
ALLOWED_WRITES: dict[tuple[str, str], str] = {}


def _name(node: ast.AST) -> str:
    """Dotted name of the receiver, as far as it can be read from the source."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _name(node.func)
    return ""


def writes_in_source(source: str, name: str) -> list[tuple[str, str]]:
    """Every ORM write in one source, as `("path:line", expression)`."""
    findings = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        receiver = _name(node.func.value)
        method = node.func.attr
        # A manager reached through a queryset chain (`Model.objects.filter(…)`) is still
        # a manager, so the whole receiver is searched, not just its tail.
        via_manager = bool(set(receiver.split(".")) & MANAGERS)
        if method in WRITE_METHODS or (method in MANAGER_WRITE_METHODS and via_manager):
            findings.append((f"{name}:{node.lineno}", f"{receiver}.{method}()"))
    return findings


def _files() -> list[Path]:
    return sorted(PRESENTATION.rglob("*.py"))


def _module_writes() -> list[tuple[str, str]]:
    findings = []
    for path in _files():
        name = path.relative_to(PRESENTATION.parent).as_posix()
        findings.extend(writes_in_source(path.read_text(encoding="utf-8"), name))
    return findings


def test_there_is_something_to_search():
    """Anti-vacuum: an empty file list would make the guard pass on nothing."""
    assert _files(), f"no .py files in {PRESENTATION}"


def test_the_detector_finds_a_write():
    """Anti-vacuum over a synthetic source, independent of the repository's state."""
    source = (
        "def view(request, form, item, context):\n"
        "    form.save()\n"
        "    item.delete()\n"
        "    Organization.objects.create(name='x')\n"
        "    Thing.objects.filter(pk=1).update(order=2)\n"
        "    context.update({'a': 1})\n"
    )
    found = [expression for _, expression in writes_in_source(source, "views.py")]
    assert found == [
        "form.save()",
        "item.delete()",
        "Organization.objects.create()",
        "Thing.objects.filter.update()",
    ], found


def test_the_presentation_does_not_write_to_the_database():
    not_allowed = [
        f"{location}: {expression}"
        for location, expression in _module_writes()
        if (location, expression) not in ALLOWED_WRITES
    ]
    assert not not_allowed, (
        f"database write in `web/` — validate the form, hand "
        f"`cleaned_data` to a domain service (CLAUDE.md, write rule): {not_allowed}"
    )


def test_the_exceptions_are_alive():
    """A stale exception quietly allows a write nobody meant to allow."""
    actual = set(_module_writes())
    errors = []
    for (location, expression), reason in ALLOWED_WRITES.items():
        if (location, expression) not in actual:
            errors.append(f"{location}: {expression} — matches no write, delete the entry")
        elif len(reason.split()) < 5:
            errors.append(f"{location}: {expression} — an exception without a written reason")
    assert not errors, errors
