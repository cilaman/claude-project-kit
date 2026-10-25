#!/usr/bin/env python3
"""PreToolUse hook: refuses a hand edit of what `scripts/check_repo.py` generates.

CI would catch the edit too — but only after a push, and the next rebuild would throw
it away without a word. Stopping the Edit/Write here costs nothing and says which flag
writes the file instead.

Active only in a repository initialised by project-kit (it has `scripts/check_repo.py`
and `backlog/tasks.tsv`); anywhere else it lets everything through. Refuses:

* any Edit/Write of `backlog/tasks.tsv` — the whole file is generated,
* an Edit/Write that changes the content between `<!-- generated: <name> -->` and
  `<!-- /generated -->` in an existing file.

Exit 2 with a reason on stderr blocks the tool call and shows the reason to Claude;
exit 0 lets it through. Any doubt (unreadable input, unknown tool) lets it through —
a hook that blocks by mistake gets switched off, and then it protects nothing.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BLOCK_RE = re.compile(r"<!-- generated: ([a-z-]+) -->\n(.*?)<!-- /generated -->", re.S)
REGISTER = "backlog/tasks.tsv"
FLAGS = {
    "active-tasks": "--rebuild-backlog",
    "archive": "--rebuild-archive",
    "requirements": "--rebuild-requirements",
    "uc-backlog": "--rebuild-uc",
}


def kit_root(path: Path) -> Path | None:
    for directory in [path.parent, *path.parents]:
        if (directory / "scripts/check_repo.py").exists() and (directory / REGISTER).exists():
            return directory
    return None


def blocks(text: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in BLOCK_RE.finditer(text)}


def edited(current: str, tool: str, data: dict) -> str | None:
    """The file as it would be after the call, or None when it cannot be told."""
    if tool == "Write":
        return data.get("content")
    edits = data.get("edits") if tool == "MultiEdit" else [data]
    text = current
    for edit in edits or ():
        old, new = edit.get("old_string"), edit.get("new_string")
        if old is None or new is None or old not in text:
            return None
        text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    return text


def verdict(payload: dict) -> str | None:
    """The reason to refuse, or None."""
    tool = payload.get("tool_name", "")
    data = payload.get("tool_input") or {}
    if tool not in {"Edit", "MultiEdit", "Write"} or not data.get("file_path"):
        return None
    path = Path(data["file_path"])
    if not path.is_absolute():
        path = Path(payload.get("cwd") or ".") / path
    root = kit_root(path.resolve())
    if root is None:
        return None
    rel = path.resolve().relative_to(root).as_posix()
    if rel == REGISTER:
        return (
            f"{REGISTER} is generated — run `python3 scripts/check_repo.py --rebuild-tasks` "
            "(or --rebuild-all) instead of editing it"
        )
    if not path.exists():
        return None
    current = path.read_text(encoding="utf-8")
    before = blocks(current)
    if not before:
        return None
    after_text = edited(current, tool, data)
    if after_text is None:
        return None
    after = blocks(after_text)
    changed = sorted(name for name in before if before[name] != after.get(name))
    if not changed:
        return None
    flags = ", ".join(f"`{FLAGS.get(name, '--rebuild-all')}`" for name in changed)
    return (
        f"{rel}: the block(s) {', '.join(changed)} are generated from the task files — "
        f"change the source (front matter of the task) and run "
        f"`python3 scripts/check_repo.py` with {flags}; the prose outside the markers "
        "may be edited"
    )


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        reason = verdict(payload)
    except (OSError, ValueError, UnicodeDecodeError):
        return 0
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
