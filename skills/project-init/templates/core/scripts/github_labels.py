"""Makes GitHub agree with the label vocabulary in .github/labels.yml.

A label born from a click in the web UI has no home in the repository: a month later
nobody can tell whether it was agreed or invented, and the vocabulary drifts one click
at a time. The file is the vocabulary; this script only applies it.

The file is complete, not additive — a label GitHub has and the file does not gets
deleted, GitHub's default set included. Two vocabularies side by side are a silent
source of inconsistency. Deleting a label strips it off every issue, so run the sync
before the queue fills up.

    python3 scripts/github_labels.py --dry-run   # what would change
    python3 scripts/github_labels.py             # change it

Needs `gh` authenticated. Standard library only: the file has one fixed shape and a
YAML dependency for it would be the only third-party import of the process scripts.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS_FILE = ROOT / ".github" / "labels.yml"

#: `key: value` inside one list item; the value may be quoted.
_FIELD_RE = re.compile(r"^\s*(?:-\s+)?(name|color|description):\s*(.*?)\s*$")


class GhError(RuntimeError):
    """`gh` is missing, not logged in, or refused a call — the script cannot go on."""


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_labels(text):
    """The vocabulary as the file writes it: name → (color, description).

    Understands exactly the shape `.github/labels.yml` uses — a `labels:` list whose
    items carry `name`, `color` and `description` — and refuses anything it cannot
    place, because a silently skipped item would be deleted from GitHub on the next run.
    """
    items, current = [], None
    for number, row in enumerate(text.splitlines(), start=1):
        stripped = row.strip()
        if not stripped or stripped.startswith("#") or stripped == "labels:":
            continue
        match = _FIELD_RE.match(row)
        if not match:
            raise ValueError(f"labels.yml:{number}: unexpected line `{stripped}`")
        key, value = match.group(1), _unquote(match.group(2))
        if stripped.startswith("-"):
            current = {}
            items.append(current)
        if current is None:
            raise ValueError(f"labels.yml:{number}: `{key}` outside a list item")
        current[key] = value
    labels = {}
    for item in items:
        if "name" not in item or "color" not in item:
            raise ValueError(f"labels.yml: item without name or color: {item}")
        if item["name"] in labels:
            raise ValueError(f"labels.yml: label `{item['name']}` is defined twice")
        labels[item["name"]] = (item["color"].lower().lstrip("#"), item.get("description", ""))
    return labels


def load_desired(path=LABELS_FILE):
    return parse_labels(path.read_text(encoding="utf-8"))


def _run(args):
    done = subprocess.run(args, capture_output=True, text=True)
    if done.returncode != 0:
        raise GhError(f"`{' '.join(args)}` failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def require_gh():
    """Both ways this script cannot run, told apart — the fix differs."""
    if shutil.which("gh") is None:
        raise GhError("`gh` is not installed")
    if subprocess.run(["gh", "auth", "status"], capture_output=True).returncode != 0:
        raise GhError("`gh` is not logged in — run `gh auth login`")


def current_labels():
    """What GitHub has right now, in the same shape as the file."""
    out = _run(["gh", "label", "list", "--limit", "200", "--json", "name,color,description"])
    return {
        item["name"]: (item["color"].lower(), item.get("description") or "")
        for item in json.loads(out)
    }


def plan(desired, current):
    """The difference as steps `(action, name, message)`."""
    steps = []
    for name, wanted in desired.items():
        if name not in current:
            steps.append(("apply", name, f"creating label `{name}`"))
        elif current[name] != wanted:
            steps.append(("apply", name, f"aligning colour and description of `{name}`"))
    for name in current:
        if name not in desired:
            steps.append(("delete", name, f"deleting label `{name}` — not in the vocabulary"))
    return steps


def apply_steps(steps, desired):
    for action, name, _ in steps:
        if action == "delete":
            _run(["gh", "label", "delete", name, "--yes"])
            continue
        color, description = desired[name]
        # `--force` is create-or-update: a label that drifted in the UI comes back to
        # the file's values instead of being reported.
        _run(
            ["gh", "label", "create", name]
            + ["--color", color, "--description", description, "--force"]
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Applies .github/labels.yml to GitHub.")
    parser.add_argument("--dry-run", action="store_true", help="only print what would change")
    args = parser.parse_args(argv)
    try:
        desired = load_desired()
        require_gh()
        steps = plan(desired, current_labels())
        for _, _, message in steps:
            print(f"  ~ {message}")
        if args.dry_run:
            print(f"github_labels: {len(steps)} change(s) proposed (--dry-run, nothing changed)")
            return 0
        apply_steps(steps, desired)
    except (GhError, ValueError) as error:
        print(f"github_labels: {error}", file=sys.stderr)
        return 1
    print(f"github_labels: {len(steps)} change(s) applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
