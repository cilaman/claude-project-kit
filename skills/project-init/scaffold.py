#!/usr/bin/env python3
"""Renders the kit's templates into a repository — the mechanical half of project-init.

    python3 scaffold.py --out ../my-repo --profiles requirements,ci-savings \
        --var PROJECT_NAME="My Project" --var GITHUB_REPO=me/my-repo ...

What it does, and nothing more (CONVENTIONS.md is the home of every rule it applies):

* collects `templates/<profile>/**` in profile order; a later profile's file replaces
  an earlier one at the same path,
* drops a file whose first line says `kit:file <condition>` when the condition is off,
* keeps or drops `kit:if <condition>` … `kit:endif` blocks and removes the markers,
* replaces `{{PLACEHOLDER}}`s and refuses to write a file with one it does not know,
* writes `X.fragment.ext` as `X.ext` when that does not exist yet, and otherwise
  parks it in `.kit-merge/` for a person (or the init skill) to merge by hand.

An existing file is never overwritten without `--force`: init runs in repositories
that already have a README or a pyproject, and silently replacing one is the kind of
loss nobody notices until much later. Translation of the prose is not done here —
that needs judgement, and judgement belongs to the skill, not to a script.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"

#: Profile order is the override order.
PROFILES = ("core", "requirements", "ci-savings", "python-django")
#: Conditions that are not profiles of their own.
SUB_OPTIONS = {"tenancy": "python-django"}

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z_]*)\}\}")
CONDITION = r"(!?[a-z][a-z-]*)"
#: A marker is a whole line, wherever it is indented — inside a function body, a
#: docstring or a YAML step — so removing it never leaves a half line behind.
BLOCK_RES = tuple(
    re.compile(
        rf"^[ \t]*{opening}kit:if {CONDITION}{closing}[ \t]*\n(.*?)"
        rf"^[ \t]*{opening}kit:endif{closing}[ \t]*\n",
        re.M | re.S,
    )
    for opening, closing in (("<!-- ", " -->"), ("# ", ""))
)
FILE_MARKER_RE = re.compile(r"^.*kit:file " + CONDITION + r".*\n")
FRAGMENT_RE = re.compile(r"^(?P<stem>.+)\.fragment(?P<suffix>\.[^.]+)$")
EXECUTABLE_DIRS = ("scripts/",)
#: Caches tools leave in the templates while somebody works on the kit — never templates.
CACHE_DIRS = {"__pycache__", ".ruff_cache", ".pytest_cache"}


class ScaffoldError(RuntimeError):
    pass


def enabled(condition: str, switched_on: set[str]) -> bool:
    negated = condition.startswith("!")
    name = condition.lstrip("!")
    if name not in PROFILES and name not in SUB_OPTIONS:
        raise ScaffoldError(f"unknown condition `{name}`")
    return (name not in switched_on) if negated else (name in switched_on)


def render(text: str, switched_on: set[str], variables: dict[str, str], origin: str) -> str | None:
    """The rendered text, or None when the whole file is conditional and switched off."""
    marker = FILE_MARKER_RE.match(text)
    if marker:
        if not enabled(marker.group(1), switched_on):
            return None
        text = text[marker.end():]
    for block_re in BLOCK_RES:
        text = block_re.sub(lambda m: m.group(2) if enabled(m.group(1), switched_on) else "", text)
    if "kit:if" in text or "kit:endif" in text:
        raise ScaffoldError(f"{origin}: unbalanced or nested kit:if block")
    unknown = sorted(set(PLACEHOLDER_RE.findall(text)) - variables.keys())
    if unknown:
        raise ScaffoldError(f"{origin}: no value for {', '.join(unknown)} (pass --var NAME=value)")
    return PLACEHOLDER_RE.sub(lambda m: variables[m.group(1)], text)


def target_path(relative: str, variables: dict[str, str]) -> str:
    src_dir = variables.get("SRC_DIR", "src").strip("/")
    if relative.startswith("src/") and src_dir != "src":
        relative = f"{src_dir}/{relative[4:]}"
    return relative


def profile_of(source: Path) -> str:
    return source.relative_to(TEMPLATES).parts[0]


def collect(profiles: list[str]) -> dict[str, Path]:
    chosen: dict[str, Path] = {}
    for profile in PROFILES:
        if profile not in profiles:
            continue
        base = TEMPLATES / profile
        for path in sorted(base.rglob("*")):
            if path.is_file() and not CACHE_DIRS & set(path.parts):
                chosen[path.relative_to(base).as_posix()] = path
    return chosen


def scaffold(out: Path, profiles: list[str], options: list[str], variables: dict[str, str],
             *, force: bool = False, dry_run: bool = False) -> dict[str, list[str]]:
    switched_on = set(profiles) | set(options)
    for option in options:
        if SUB_OPTIONS.get(option) not in profiles:
            raise ScaffoldError(f"`{option}` needs the profile `{SUB_OPTIONS.get(option)}`")
    report: dict[str, list[str]] = {"written": [], "skipped": [], "merge": [], "dropped": []}
    for relative, source in collect(profiles).items():
        origin = f"{profile_of(source)}/{relative}"
        text = render(source.read_text(encoding="utf-8"), switched_on, variables, origin)
        if text is None:
            report["dropped"].append(relative)
            continue
        relative = target_path(relative, variables)
        fragment = FRAGMENT_RE.match(Path(relative).name)
        if fragment:
            whole = str(Path(relative).with_name(fragment["stem"] + fragment["suffix"]))
            if (out / whole).exists():
                parked = f".kit-merge/{whole}"
                report["merge"].append(f"{parked} → {whole}")
                relative = parked
            else:
                relative = whole
        target = out / relative
        if target.exists() and not force and not relative.startswith(".kit-merge/"):
            report["skipped"].append(relative)
            continue
        report["written"].append(relative)
        if dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        if relative.startswith(EXECUTABLE_DIRS) and relative.endswith((".py", ".sh")):
            target.chmod(0o755)
    return report


def parse_variables(pairs: list[str], json_file: str | None) -> dict[str, str]:
    variables: dict[str, str] = {}
    if json_file:
        variables.update(json.loads(Path(json_file).read_text(encoding="utf-8")))
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep:
            raise ScaffoldError(f"--var expects NAME=value, got `{pair}`")
        variables[name] = value
    return {name: str(value) for name, value in variables.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="root of the target repository")
    parser.add_argument(
        "--profiles", default="", help="comma list beyond core: " + ", ".join(PROFILES[1:])
    )
    parser.add_argument(
        "--options", default="", help="comma list of sub-options: " + ", ".join(SUB_OPTIONS)
    )
    parser.add_argument("--var", action="append", default=[], help="NAME=value, repeatable")
    parser.add_argument("--vars", help="JSON file with {NAME: value}")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    parser.add_argument("--dry-run", action="store_true", help="report only")
    args = parser.parse_args(argv)
    try:
        profiles = ["core"] + [p for p in args.profiles.split(",") if p and p != "core"]
        for profile in profiles:
            if profile not in PROFILES:
                raise ScaffoldError(f"unknown profile `{profile}`")
        options = [o for o in args.options.split(",") if o]
        out = Path(args.out).resolve()
        if not out.is_dir():
            raise ScaffoldError(f"{out} is not a directory")
        report = scaffold(out, profiles, options, parse_variables(args.var, args.vars),
                          force=args.force, dry_run=args.dry_run)
    except (ScaffoldError, json.JSONDecodeError, OSError) as error:
        print(f"scaffold: {error}", file=sys.stderr)
        return 1
    for kind in ("written", "skipped", "merge", "dropped"):
        for item in report[kind]:
            print(f"{kind:>8}  {item}")
    print(
        f"scaffold: {len(report['written'])} written, {len(report['skipped'])} skipped (exist), "
        f"{len(report['merge'])} to merge by hand, {len(report['dropped'])} dropped"
        + (" — dry run" if args.dry_run else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
