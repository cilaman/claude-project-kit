"""Layering guard — the domain does not know HTTP.

Hard rule in CLAUDE.md and docs/architecture.md: the presentation module
`{{PRESENTATION_MODULE}}/` may call domain modules, a domain module must not depend on
`{{PRESENTATION_MODULE}}/`. That is the price of later separability: once an `api/`, a
management command or a queue appears next to it, the domain must work unchanged.

Three spellings of the same dependency, each guarded separately because each is
invisible to the others: a Python import, a route name (`reverse("…:name")` imports
only `django`), and a `{% load %}` of the presentation's tag library in a template.

The tests read source, not runtime imports: a violation is caught even in code that
is never called.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "{{SRC_DIR}}"
PRESENTATION_MODULE = "{{PRESENTATION_MODULE}}"

#: Every package in the source root except the presentation layer and the project
#: package, which necessarily knows the presentation (it assembles the URL conf).
DOMAIN_MODULES = sorted(
    path.name
    for path in SRC.iterdir()
    if path.is_dir()
    and path.name not in {PRESENTATION_MODULE, "{{DJANGO_PROJECT}}"}
    and (path / "__init__.py").exists()
)

#: How a route of the presentation layer is named in `reverse()` and `{% url %}`.
ROUTE_NAMES = (f'"{PRESENTATION_MODULE}:', f"'{PRESENTATION_MODULE}:")


def imported_roots(source: str) -> set[str]:
    """Roots of every absolute module the source imports."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_domain_modules_exist():
    """Anti-vacuum: an empty module list would make every test below pass on nothing."""
    assert DOMAIN_MODULES, f"no domain packages in {SRC}"


def test_the_detector_finds_an_import():
    """Anti-vacuum: the reader really sees both import forms."""
    source = f"import {PRESENTATION_MODULE}.views\nfrom {PRESENTATION_MODULE} import forms\n"
    assert PRESENTATION_MODULE in imported_roots(source)
    assert PRESENTATION_MODULE in imported_roots(f"from {PRESENTATION_MODULE}.forms import X\n")


@pytest.mark.parametrize("module", DOMAIN_MODULES)
def test_a_domain_module_does_not_import_the_presentation(module):
    for path in sorted((SRC / module).rglob("*.py")):
        roots = imported_roots(path.read_text(encoding="utf-8"))
        assert PRESENTATION_MODULE not in roots, (
            f"{path.relative_to(SRC)} imports `{PRESENTATION_MODULE}` — the domain must "
            "not know the presentation layer (CLAUDE.md, layering rule)"
        )


def test_the_namespace_is_what_this_module_thinks_it_is():
    """Anti-vacuum: if `app_name` changed, the guard below would look for a dead string."""
    urls = SRC / PRESENTATION_MODULE / "urls.py"
    if not urls.exists():
        pytest.skip(f"{PRESENTATION_MODULE}/urls.py does not exist yet")
    assert f'app_name = "{PRESENTATION_MODULE}"' in urls.read_text(encoding="utf-8"), (
        f'{PRESENTATION_MODULE}/urls.py does not declare app_name = "{PRESENTATION_MODULE}" — '
        "the guard below would be watching a string nobody writes"
    )


@pytest.mark.parametrize("module", DOMAIN_MODULES)
def test_a_domain_module_does_not_name_presentation_routes(module):
    """`reverse("<presentation>:…")` is a runtime dependency the import guard cannot see.

    Textual on purpose, so it covers templates and catches a mention in a comment too:
    prose quoting the namespace is how the literal creeps back. A domain that needs a
    URL (a link in an e-mail) asks a registry the presentation fills at startup.
    """
    findings = [
        str(path.relative_to(SRC))
        for path in sorted((SRC / module).rglob("*"))
        if path.is_file()
        and path.suffix in {".py", ".html", ".txt"}
        and any(marker in path.read_text(encoding="utf-8") for marker in ROUTE_NAMES)
    ]
    assert not findings, (
        f"a domain module names a route of `{PRESENTATION_MODULE}`: {', '.join(findings)}"
    )


def test_a_domain_template_does_not_load_presentation_tags():
    """`{% load %}` runs the presentation layer at render time — the same dependency."""
    tags = SRC / PRESENTATION_MODULE / "templatetags"
    libraries = sorted(p.stem for p in tags.glob("*.py") if p.stem != "__init__")
    if not libraries:
        pytest.skip(f"{PRESENTATION_MODULE}/templatetags has no tag library yet")
    findings = []
    for module in DOMAIN_MODULES:
        for path in sorted((SRC / module).rglob("*")):
            if not path.is_file() or path.suffix not in {".html", ".txt"}:
                continue
            for match in re.finditer(r"\{%\s*load\s+([^%]+?)\s*%\}", path.read_text("utf-8")):
                loaded = set(match.group(1).split()) & set(libraries)
                if loaded:
                    findings.append(f"{path.relative_to(SRC)}: {', '.join(sorted(loaded))}")
    assert not findings, (
        f"a domain template loads a tag library of `{PRESENTATION_MODULE}/`: {'; '.join(findings)}"
    )
