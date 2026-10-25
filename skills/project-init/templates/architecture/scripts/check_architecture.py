#!/usr/bin/env python3
"""Guards the architecture rules of `architecture.toml`, in any language.

The rules every codebase needs are the same whatever the stack: a layer does not reach
into a layer it must not know, a construct forbidden in some place appears there only
as a named exception with its reason, and a skipped test is a decision with somebody
answering the question instead. What differs between stacks is only how an import or
a skip is spelled — so that is all this script knows per language (the presets below),
and everything about *this* project lives in `architecture.toml`, its one home.

    python3 scripts/check_architecture.py                # check
    python3 scripts/check_architecture.py --list-files   # which layer each file falls in

**These guards are textual.** They read words, not behaviour: an import built at run
time, a write behind a helper or a skip in a fixture are invisible to them. That is the
price of working for every language, and it is said here so nobody mistakes it for
more. A stronger, stack-native guard (an AST walk, a query of the database catalog)
belongs next to this one wherever an invariant is worth it — skill `guard`.

Every rule also proves it is not guarding an empty set: a layer must match files (or
say why it does not yet), a forbidden pattern must match its own `example`, and an
exception or a declared skip that no longer matches anything fails — a stale
exception quietly allows what nobody meant to allow.

Standard library only (Python 3.11+ for `tomllib`). Exit 0 = OK, 1 = violations.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
CONFIG = "architecture.toml"

#: Directories that are never the project's own source.
ALWAYS_EXCLUDED = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "target",
    "build",
    "dist",
    "__pycache__",
    ".gradle",
    ".idea",
    "bin",
    "obj",
    ".next",
    ".nuxt",
    "coverage",
}

#: How each language spells an import. Group 1 is the imported module or path.
#: A preset is a claim about a language's syntax; `tests/scripts/test_check_architecture.py`
#: holds each one to an example.
IMPORT_PRESETS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "python": (
        (".py",),
        (r"^\s*import\s+([A-Za-z_][\w.]*)", r"^\s*from\s+([A-Za-z_][\w.]*)\s+import\b"),
    ),
    "javascript": (
        (".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"),
        (
            r"""\bimport\s+(?:[\w$*{}\s,]+\s+from\s+)?['"]([^'"]+)['"]""",
            r"""\bexport\s+[\w$*{}\s,]+\s+from\s+['"]([^'"]+)['"]""",
            r"""\b(?:require|import)\(\s*['"]([^'"]+)['"]\s*\)""",
        ),
    ),
    "java": ((".java",), (r"^\s*import\s+(?:static\s+)?([\w.]+)",)),
    "kotlin": ((".kt", ".kts"), (r"^\s*import\s+([\w.]+)",)),
    "csharp": ((".cs",), (r"^\s*(?:global\s+)?using\s+(?:static\s+)?([\w.]+)\s*;",)),
    #: Go groups imports in a block; a pattern with the group `block` is read for every
    #: quoted path inside it, so a string literal elsewhere is never taken for an import.
    "go": (
        (".go",),
        (r'^\s*import\s+(?:[\w.]+\s+)?"([^"]+)"', r"(?s)^import\s*\((?P<block>.*?)^\)"),
    ),
    "rust": (
        (".rs",),
        (r"^\s*(?:pub(?:\([\w ]+\))?\s+)?use\s+([\w:]+)", r"^\s*extern\s+crate\s+(\w+)"),
    ),
    "php": ((".php",), (r"^\s*use\s+(?:function\s+|const\s+)?\\?([\w\\]+)",)),
    "ruby": ((".rb",), (r"""^\s*require(?:_relative)?\s+['"]([^'"]+)['"]""",)),
}
IMPORT_PRESETS["typescript"] = ((".ts", ".tsx", ".mts", ".cts"), IMPORT_PRESETS["javascript"][1])

#: How each language spells skipping a test. A match is a skip to be declared.
SKIP_PRESETS: dict[str, tuple[str, ...]] = {
    "python": (
        r"\bpytest\.skip\(",
        r"@pytest\.mark\.skip(?:if)?\b",
        r"\bpytest\.importorskip\(",
        r"@unittest\.skip\w*",
        r"\bself\.skipTest\(",
    ),
    "javascript": (r"\b(?:it|test|describe)\.(?:skip|todo)\(", r"\bx(?:it|test|describe)\("),
    "java": (
        r"@Disabled\b",
        r"@Ignore\b",
        r"\bAssumptions?\.assume\w*\(",
        r"\bassume(?:True|False)\(",
    ),
    "kotlin": (r"@Disabled\b", r"@Ignore\b"),
    "csharp": (r"\bSkip\s*=", r"\[Ignore\b"),
    "go": (r"\bt\.Skip(?:f|Now)?\(",),
    "rust": (r"#\[ignore\b",),
    "php": (r"\bmarkTest(?:Skipped|Incomplete)\(", r"@group\s+skip"),
    "ruby": (r"^\s*(?:skip|pending)\b", r"\bx(?:it|describe|context)\b"),
}
SKIP_PRESETS["typescript"] = SKIP_PRESETS["javascript"]

SKIP_CATEGORIES = {
    "commit": "another environment of the commit run answers it (CI has the service)",
    "regression": "the weekly regression run answers it",
    "dormant": "the set the test walks is empty today; it comes back when it fills",
    "data": "the committed sample does not carry the case",
}
MIN_REASON_WORDS = 5


# --- Paths ---------------------------------------------------------------------------


def glob_regex(pattern: str) -> re.Pattern:
    """`**` crosses directories, `*` and `?` do not — the shape everyone expects."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(f"^{out}$")


def matches(path: str, patterns: list[str]) -> bool:
    return any(glob_regex(pattern).match(path) for pattern in patterns)


def project_files(root: Path, exclude: list[str]) -> list[str]:
    """Files of this checkout, POSIX-relative; nested checkouts (worktrees) are skipped."""
    found = []
    for directory, subdirectories, files in os.walk(root):
        here = Path(directory)
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if name not in ALWAYS_EXCLUDED and not (here / name / ".git").exists()
        )
        for name in files:
            rel = (here / name).relative_to(root).as_posix()
            if not matches(rel, exclude):
                found.append(rel)
    return sorted(found)


# --- Configuration -------------------------------------------------------------------


@dataclass
class Layer:
    name: str
    paths: list[str]
    imports: list[str]
    may_use: list[str]
    empty: str = ""


@dataclass
class Allowance:
    path: str
    match: str
    reason: str


@dataclass
class Forbidden:
    name: str
    reason: str
    paths: list[str]
    pattern: re.Pattern
    example: str
    allowed: list[Allowance] = field(default_factory=list)


@dataclass
class Config:
    languages: list[str]
    exclude: list[str]
    layers: list[Layer]
    forbidden: list[Forbidden]
    skip_paths: list[str]
    skip_patterns: list[re.Pattern]
    declared_skips: list[tuple[Allowance, str]]
    ascii_paths: list[str]
    import_patterns: list[tuple[tuple[str, ...], list[re.Pattern]]]
    problems: list[str]


def load(root: Path) -> Config:
    problems: list[str] = []
    path = root / CONFIG
    if not path.exists():
        return Config([], [], [], [], [], [], [], [], [], [f"{CONFIG} is missing"])
    data = tomllib.loads(path.read_text(encoding="utf-8"))

    languages = list(data.get("languages", []))
    for language in languages:
        if language not in IMPORT_PRESETS:
            problems.append(
                f"{CONFIG}: unknown language `{language}` ({', '.join(sorted(IMPORT_PRESETS))})"
            )
    import_patterns = [
        (IMPORT_PRESETS[lang][0], [re.compile(p, re.M) for p in IMPORT_PRESETS[lang][1]])
        for lang in languages
        if lang in IMPORT_PRESETS
    ]
    for custom in data.get("import_patterns", []):
        import_patterns.append((tuple(custom["extensions"]), [re.compile(custom["pattern"], re.M)]))

    layers = [
        Layer(
            name=item["name"],
            paths=list(item.get("paths", [])),
            imports=list(item.get("imports", [])),
            may_use=list(item.get("may_use", [])),
            empty=item.get("empty", ""),
        )
        for item in data.get("layers", [])
    ]
    names = [layer.name for layer in layers]
    for layer in layers:
        for used in layer.may_use:
            if used not in names:
                problems.append(
                    f"{CONFIG}: layer `{layer.name}` may use `{used}`, which is no layer"
                )

    forbidden = []
    for item in data.get("forbidden", []):
        rule = Forbidden(
            name=item["name"],
            reason=item.get("reason", ""),
            paths=list(item.get("paths", [])),
            pattern=re.compile(item["pattern"]),
            example=item.get("example", ""),
            allowed=[
                Allowance(a["path"], a["match"], a.get("reason", ""))
                for a in item.get("allowed", [])
            ],
        )
        forbidden.append(rule)

    skips = data.get("skips", {})
    skip_patterns = [re.compile(p, re.M) for lang in languages for p in SKIP_PRESETS.get(lang, ())]
    skip_patterns += [re.compile(p, re.M) for p in skips.get("patterns", [])]
    declared = [
        (Allowance(d["path"], d["match"], d.get("answers", "")), d.get("category", ""))
        for d in skips.get("declared", [])
    ]
    return Config(
        languages=languages,
        exclude=list(data.get("exclude", [])),
        layers=layers,
        forbidden=forbidden,
        skip_paths=list(skips.get("paths", [])),
        skip_patterns=skip_patterns,
        declared_skips=declared,
        ascii_paths=list(data.get("ascii_paths", [])),
        import_patterns=import_patterns,
        problems=problems,
    )


# --- Checks --------------------------------------------------------------------------


def layer_of_file(path: str, layers: list[Layer]) -> Layer | None:
    """First layer whose paths match — order in the file is precedence."""
    return next((layer for layer in layers if matches(path, layer.paths)), None)


def layer_of_import(target: str, source: str, layers: list[Layer]) -> Layer | None:
    """The layer an import names: a relative path is resolved, a name is read by prefix."""
    if target.startswith("."):
        resolved = os.path.normpath(str(PurePosixPath(source).parent / target)).replace("\\", "/")
        # An import names a module, not always a file: try it as written, with the
        # extension of the importing file, and as a directory's index.
        suffix = PurePosixPath(source).suffix
        for candidate in (resolved, resolved + suffix, f"{resolved}/index{suffix}"):
            layer = layer_of_file(candidate, layers)
            if layer:
                return layer
        return None
    for layer in layers:
        for prefix in layer.imports:
            if target == prefix or re.match(re.escape(prefix) + r"[./:\\]", target):
                return layer
    return None


BLOCK_ITEM_RE = re.compile(r'"([^"]+)"')


def imports_in(text: str, patterns: list[re.Pattern]) -> list[tuple[int, str]]:
    found = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            if "block" in pattern.groupindex:
                start = match.start("block")
                for item in BLOCK_ITEM_RE.finditer(match.group("block")):
                    found.append((text.count("\n", 0, start + item.start()) + 1, item.group(1)))
            else:
                found.append((text.count("\n", 0, match.start()) + 1, match.group(1)))
    return sorted(set(found))


def layer_problems(root: Path, files: list[str], config: Config) -> list[str]:
    problems = []
    for layer in config.layers:
        if not any(matches(path, layer.paths) for path in files) and not layer.empty:
            problems.append(
                f"{CONFIG}: layer `{layer.name}` matches no file — fix its paths, or say why "
                'with `empty = "…"` (a guard over nothing passes forever)'
            )
    for path in files:
        layer = layer_of_file(path, config.layers)
        if layer is None:
            continue
        patterns = [p for exts, ps in config.import_patterns if path.endswith(exts) for p in ps]
        if not patterns:
            continue
        text = (root / path).read_text(encoding="utf-8", errors="replace")
        for line, target in imports_in(text, patterns):
            used = layer_of_import(target, path, config.layers)
            if used and used.name != layer.name and used.name not in layer.may_use:
                problems.append(
                    f"{path}:{line}: layer `{layer.name}` imports `{target}` of layer "
                    f"`{used.name}` (may use: {', '.join(layer.may_use) or 'nothing'})"
                )
    return problems


def _lines(root: Path, path: str):
    text = (root / path).read_text(encoding="utf-8", errors="replace")
    return enumerate(text.splitlines(), start=1)


def forbidden_problems(root: Path, files: list[str], config: Config) -> list[str]:
    problems = []
    for rule in config.forbidden:
        where = f"{CONFIG}: forbidden `{rule.name}`"
        if len(rule.reason.split()) < MIN_REASON_WORDS:
            problems.append(f"{where} has no reason — a rule nobody can explain gets switched off")
        if not rule.example or not rule.pattern.search(rule.example):
            problems.append(
                f"{where}: the pattern does not match its own `example` — it may guard nothing"
            )
        scope = [path for path in files if matches(path, rule.paths)]
        if not scope:
            problems.append(f"{where} covers no file — fix its paths")
        used = set()
        for path in scope:
            for number, line in _lines(root, path):
                if not rule.pattern.search(line):
                    continue
                allowed = next(
                    (i for i, a in enumerate(rule.allowed) if a.path == path and a.match in line),
                    None,
                )
                if allowed is None:
                    problems.append(
                        f"{path}:{number}: forbidden `{rule.name}` — {rule.reason} ({line.strip()})"
                    )
                else:
                    used.add(allowed)
        for index, exception in enumerate(rule.allowed):
            if index not in used:
                problems.append(
                    f"{where}: exception {exception.path} `{exception.match}` "
                    "matches nothing — delete it"
                )
            if len(exception.reason.split()) < MIN_REASON_WORDS:
                problems.append(f"{where}: exception {exception.path} has no written reason")
    return problems


def skip_problems(root: Path, files: list[str], config: Config) -> list[str]:
    if not config.skip_paths:
        return []
    problems, used = [], set()
    scope = [path for path in files if matches(path, config.skip_paths)]
    for path in scope:
        for number, line in _lines(root, path):
            if not any(pattern.search(line) for pattern in config.skip_patterns):
                continue
            declared = next(
                (
                    i
                    for i, (d, _) in enumerate(config.declared_skips)
                    if d.path == path and d.match in line
                ),
                None,
            )
            if declared is None:
                problems.append(
                    f"{path}:{number}: undeclared skip — a skipped test reports success; declare "
                    f"it in {CONFIG} [[skips.declared]] with who answers instead ({line.strip()})"
                )
            else:
                used.add(declared)
    for index, (skip, category) in enumerate(config.declared_skips):
        if index not in used:
            problems.append(
                f"{CONFIG}: declared skip {skip.path} `{skip.match}` matches nothing — delete it"
            )
        if category not in SKIP_CATEGORIES:
            problems.append(
                f"{CONFIG}: skip {skip.path} has category `{category}` "
                f"({', '.join(SKIP_CATEGORIES)})"
            )
        if len(skip.reason.split()) < MIN_REASON_WORDS:
            problems.append(
                f"{CONFIG}: skip {skip.path} does not say who answers instead (`answers`)"
            )
    return problems


def ascii_problems(files: list[str], config: Config) -> list[str]:
    return [
        f"{path}: file name is not ASCII (language policy, CLAUDE.md rule 1)"
        for path in files
        if matches(path, config.ascii_paths) and not path.isascii()
    ]


def check(root: Path) -> list[str]:
    config = load(root)
    if not (config.layers or config.forbidden or config.skip_paths or config.ascii_paths):
        return config.problems + [
            f"{CONFIG} declares no rule — the hard rules it backs guard nothing"
        ]
    files = project_files(root, config.exclude)
    return (
        config.problems
        + layer_problems(root, files, config)
        + forbidden_problems(root, files, config)
        + skip_problems(root, files, config)
        + ascii_problems(files, config)
    )


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list-files", action="store_true", help="print the layer of every file")
    args = parser.parse_args(argv)
    if args.list_files:
        config = load(root)
        for path in project_files(root, config.exclude):
            layer = layer_of_file(path, config.layers)
            print(f"{layer.name if layer else '-':<16} {path}")
        return 0
    problems = check(root)
    if problems:
        for problem in problems:
            print(f"  ✗ {problem}", file=sys.stderr)
        print(f"check_architecture: {len(problems)} violation(s)", file=sys.stderr)
        return 1
    print("check_architecture: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
