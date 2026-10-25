#!/usr/bin/env python3
"""Checks the structure of the repository and keeps its generated parts in step.

Guards the hard rules of CLAUDE.md that a machine can read: the backlog conventions,
the header block of every document, the doc map, relative links, and the generated
indexes. Standard library only — it runs under bare `python3`, offline, in CI and
before every commit, so it must not need a virtualenv or the network.

Checks:

1. the mandatory files and directories exist,
2. every task file `backlog/BL-*.md` (including `done/`): file name, front matter with
   the required keys in the fixed order, an id matching the file name, valid status,
   priority and date, closed tasks living in `done/` and only there, unique ids,
3. `depends_on:` names tasks that exist and forms no cycle,
4. every relative Markdown link points at a file that exists,
5. every document under `docs/` has a header block and is reachable from the doc map,
6. the generated block of `backlog/BACKLOG.md`, the register `backlog/tasks.tsv` and
   the archive `backlog/DONE.md` agree with the task files,
7. with the requirements layer on: `parent:` names a requirement with a prose file,
   `uc:` names a use case of the catalog, the generated requirements overview and the
   State column of the catalog agree with the backlog,
8. an active task has an open GitHub issue of its number and, on the main line, a
   closed task has none — only when `gh` is there; otherwise it says nobody looked,
9. nothing is left over from initialisation (placeholders, conditional markers).

What is computable is never typed by hand. The rebuild flags rewrite the generated
parts from the task files; `--rebuild-all` runs every one the enabled layers have,
plus `--fix-links`, which is what closing a task needs.

Exit 0 = OK, exit 1 = violations (printed to stderr).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Optional layers. Set at initialisation and changed only by a decision written here:
#: a layer that switched itself off because a file went missing would stop checking
#: without a word, which is the one failure a check must never have.
REQUIREMENTS_LAYER = False
# kit:if requirements
REQUIREMENTS_LAYER = True
# kit:endif

MAIN_BRANCH = "{{MAIN_BRANCH}}"

#: The first task number that is also an issue number. Raise it when a repository
#: adopts the method late and the numbers below were spent before the identity held.
SERIES_FIRST_NUMBER = 1

BACKLOG_DIR = "backlog"
DONE_DIR = f"{BACKLOG_DIR}/done"
INDEX_FILE = f"{BACKLOG_DIR}/BACKLOG.md"
ARCHIVE_FILE = f"{BACKLOG_DIR}/DONE.md"
REGISTER_FILE = f"{BACKLOG_DIR}/tasks.tsv"
DOC_MAP = "docs/index.md"
REQUIREMENTS_FILE = "docs/requirements.md"
REQUIREMENTS_DIR = "docs/requirements"
CATALOGUE_FILE = "docs/use-cases.md"

REQUIRED_PATHS = [
    "CLAUDE.md",
    "README.md",
    DOC_MAP,
    "docs/documentation-principles.md",
    "docs/decisions",
    "docs/decisions/task-tracking.md",
    INDEX_FILE,
    ARCHIVE_FILE,
    REGISTER_FILE,
    f"{BACKLOG_DIR}/_TEMPLATE.md",
    DONE_DIR,
    "scripts/check_repo.py",
    ".github/workflows/ci.yml",
    ".github/workflows/task-lifecycle.yml",
    #: The three files the task lifecycle stands on: the issue forms, the one home of
    #: the label vocabulary, and the PR template carrying `Closes #NN`.
    ".github/ISSUE_TEMPLATE",
    ".github/labels.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
]
REQUIRED_PATHS_REQUIREMENTS = [REQUIREMENTS_FILE, REQUIREMENTS_DIR, CATALOGUE_FILE]

#: Words the generated tables print. They are documentation, so initialisation
#: translates them into the language of the docs; the State words are also what the
#: catalog check compares against, so translate them here and nowhere else.
LABELS = {
    "id": "ID",
    "task": "Task",
    "priority": "Priority",
    "status": "Status",
    "delivered_on": "Delivered",
    "requirement": "Requirement",
    "state": "State",
    "wave": "Wave",
    "done": "Done",
    "items": "Items",
    "uc": "UC",
    "task_status": "Task status",
    "not_started": "not started",
    "in_progress": "in progress",
    "delivered": "delivered",
    "cancelled": "cancelled",
}
STATUS_ICONS = {
    "NEW": "🆕",
    "IN_PROGRESS": "🔵",
    "NEEDS_INPUT": "🟡",
    "BLOCKED": "🟠",
    "DONE": "🟢",
    "OBSOLETE": "⚪",
}

STATUSES = set(STATUS_ICONS)
#: Closed statuses live in `done/` and only there. OBSOLETE is closed like DONE: the
#: file is never deleted, because why something is not being done is history too.
CLOSED_STATUSES = {"DONE", "OBSOLETE"}
PRIORITIES = ("P1", "P2", "P3")
NONE_VALUE = "—"

#: The fixed order of the front matter. A key out of order is reported because the
#: order is what makes a copied template keep the keys a reader expects at the bottom.
KEY_ORDER = (
    "id",
    "title",
    "priority",
    "status",
    "created",
    "parent",
    "depends_on",
    "source",
    "status_note",
    "result_note",
    "uc",
)
REQUIRED_KEYS = {"id", "title", "priority", "status", "created", "source"}
#: An active task says what it stands on even when the answer is `—`: the index is
#: ordered by `depends_on:`, and a missing key reads exactly like "stands on nothing".
REQUIRED_KEYS_ACTIVE = {"depends_on"}
REQUIRED_KEYS_REQUIREMENTS = {"parent", "uc"}

TASK_NAME_RE = re.compile(r"^(BL-(\d+))-[a-z0-9][a-z0-9-]*\.md$")
RQ_NAME_RE = re.compile(r"^(RQ-(\d+))-[a-z0-9][a-z0-9-]*\.md$")
BL_LIST_RE = re.compile(r"^BL-\d+(?:, BL-\d+)*$")
UC_LIST_RE = re.compile(r"^UC-\d+(?:, UC-\d+)*$")
RQ_RE = re.compile(r"^RQ-\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEY_RE = re.compile(r"^([a-z_]+):\s*(.*)$")
FOLD_MARKERS = {">", ">-", ">+"}
GENERATED_RE_TEMPLATE = r"(<!-- generated: {name} -->\n)(.*?)(<!-- /generated -->)"

IGNORED_DIRS = (".git", ".venv", "node_modules", "__pycache__")

GH_TIMEOUT_SECONDS = 15
GH_ISSUE_LIST = ("gh", "issue", "list", "--state", "open", "--limit", "1000", "--json", "number")


# --- Reading the backlog -------------------------------------------------------------


@dataclass(frozen=True)
class Task:
    id: str
    number: int
    title: str
    priority: str
    status: str
    parent: str
    depends_on: tuple[str, ...]
    uc: tuple[str, ...]
    status_note: str
    result_note: str
    path: str  # relative to the root, POSIX
    in_done: bool

    @property
    def closed(self) -> bool:
        return self.status in CLOSED_STATUSES


def _strip_comment(value: str) -> str:
    """A value without its trailing `  # comment` — the template carries those."""
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def front_matter(text: str) -> tuple[dict[str, str] | None, list[str]]:
    """The front matter as an ordered dict, and what is wrong with its shape.

    A small subset of YAML on purpose — `key: value`, inline comments and folded
    scalars (`>`) — so the script needs nothing outside the standard library.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, []
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None, ["the front matter is not closed by `---`"]
    data: dict[str, str] = {}
    problems: list[str] = []
    key, folded = None, None
    for line in lines[1:end]:
        if folded is not None:
            if line.startswith((" ", "\t")) or not line.strip():
                folded.append(line.strip())
                continue
            data[key] = " ".join(part for part in folded if part)
            folded = None
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = KEY_RE.match(line)
        if not match:
            problems.append(f"front matter line is not `key: value`: {line!r}")
            continue
        key, value = match.group(1), _strip_comment(match.group(2))
        if key in data:
            problems.append(f"front matter key `{key}` appears twice")
        if value in FOLD_MARKERS:
            folded = []
            data[key] = ""
            continue
        data[key] = value
    if folded is not None:
        data[key] = " ".join(part for part in folded if part)
    return data, problems


def _split(value: str) -> tuple[str, ...]:
    if not value or value == NONE_VALUE:
        return ()
    return tuple(part.strip() for part in value.split(","))


def number_of(item_id: str) -> int:
    return int(item_id.split("-", 1)[1])


def _task_files(root: Path) -> list[tuple[Path, bool]]:
    backlog = root / BACKLOG_DIR
    files = [(path, False) for path in sorted(backlog.glob("BL-*.md"))]
    done = root / DONE_DIR
    if done.is_dir():
        files += [(path, True) for path in sorted(done.glob("BL-*.md"))]
    return files


def read_task(root: Path, path: Path, in_done: bool) -> tuple[Task | None, list[str]]:
    """One task file, checked on its own; the whole-backlog questions come later."""
    rel = path.relative_to(root).as_posix()
    name = TASK_NAME_RE.match(path.name)
    if not name:
        return None, [f"{rel}: file name does not follow BL-NN-kebab-slug.md"]
    data, shape = front_matter(path.read_text(encoding="utf-8"))
    if data is None:
        return None, [f"{rel}: front matter block (--- … ---) is missing", *shape]
    problems = [f"{rel}: {problem}" for problem in shape]

    required = set(REQUIRED_KEYS)
    if not in_done:
        required |= REQUIRED_KEYS_ACTIVE
    if REQUIREMENTS_LAYER:
        required |= REQUIRED_KEYS_REQUIREMENTS
    missing = required - data.keys()
    if missing:
        problems.append(f"{rel}: front matter lacks keys: {', '.join(sorted(missing))}")
    unknown = [key for key in data if key not in KEY_ORDER]
    if unknown:
        problems.append(f"{rel}: unknown front matter keys: {', '.join(unknown)}")
    known = [key for key in data if key in KEY_ORDER]
    if known != sorted(known, key=KEY_ORDER.index):
        problems.append(f"{rel}: front matter keys out of order (expected {', '.join(KEY_ORDER)})")

    task_id = data.get("id", "")
    if task_id != name.group(1):
        problems.append(f"{rel}: id `{task_id}` does not match the file name")
    status = data.get("status", "")
    if status not in STATUSES:
        problems.append(f"{rel}: unknown status `{status}` ({', '.join(sorted(STATUSES))})")
    priority = data.get("priority", "")
    if priority not in PRIORITIES:
        problems.append(f"{rel}: unknown priority `{priority}` ({', '.join(PRIORITIES)})")
    if not DATE_RE.match(data.get("created", "")):
        problems.append(f"{rel}: `created` is not YYYY-MM-DD")
    if in_done and status not in CLOSED_STATUSES:
        problems.append(f"{rel}: lies in done/ but its status is `{status}`")
    if not in_done and status in CLOSED_STATUSES:
        problems.append(f"{rel}: status is {status} but the file is not in done/")
    for key, pattern in (("depends_on", BL_LIST_RE), ("uc", UC_LIST_RE)):
        value = data.get(key, NONE_VALUE)
        if value != NONE_VALUE and not pattern.match(value):
            problems.append(f"{rel}: `{key}: {value}` is neither `{NONE_VALUE}` nor a list")
        elif value != NONE_VALUE and list(_split(value)) != sorted(_split(value), key=number_of):
            problems.append(f"{rel}: `{key}:` is not in ascending order")
    parent = data.get("parent", NONE_VALUE)
    if parent != NONE_VALUE and not RQ_RE.match(parent):
        problems.append(f"{rel}: `parent: {parent}` is neither `{NONE_VALUE}` nor RQ-NN")

    task = Task(
        id=name.group(1),
        number=int(name.group(2)),
        title=data.get("title", ""),
        priority=priority,
        status=status,
        parent=parent,
        depends_on=_split(data.get("depends_on", NONE_VALUE)),
        uc=_split(data.get("uc", NONE_VALUE)),
        status_note=data.get("status_note", ""),
        result_note=data.get("result_note", ""),
        path=rel,
        in_done=in_done,
    )
    return task, problems


def load_tasks(root: Path) -> tuple[list[Task], list[str]]:
    tasks, problems = [], []
    for path, in_done in _task_files(root):
        task, found = read_task(root, path, in_done)
        problems += found
        if task:
            tasks.append(task)
    by_id: dict[str, list[str]] = {}
    for task in tasks:
        by_id.setdefault(task.id, []).append(task.path)
    for task_id, paths in sorted(by_id.items()):
        if len(paths) > 1:
            problems.append(f"duplicate id `{task_id}`: {', '.join(paths)}")
    return sorted(tasks, key=lambda task: task.number), problems


# --- Generated blocks ----------------------------------------------------------------


def generated_block(text: str, name: str) -> re.Match | None:
    return re.search(GENERATED_RE_TEMPLATE.format(name=re.escape(name)), text, re.S)


def replace_block(text: str, name: str, lines: list[str]) -> str | None:
    """The text with the block rewritten, or None when the markers are missing."""
    match = generated_block(text, name)
    if not match:
        return None
    body = "".join(f"{line}\n" for line in lines)
    return text[: match.start(2)] + body + text[match.end(2) :]


def cell(text: str) -> str:
    return re.sub(r"\s*\n\s*", " ", text).replace("|", "\\|").strip()


def _href(task: Task, base: str) -> str:
    return os.path.relpath(task.path, base).replace("\\", "/")


def _block_differences(path: str, name: str, text: str, expected: list[str], flag: str):
    """Row-level report of a drifted block, so the fix is not a hunt."""
    match = generated_block(text, name)
    if not match:
        return [f"{path}: generated block `{name}` is missing its markers"]
    actual = match.group(2).splitlines()
    if actual == expected:
        return []
    problems = []
    key = re.compile(r"^\|\s*\[?((?:BL|RQ)-\d+)")
    actual_rows = {m.group(1): row for row in actual if (m := key.match(row))}
    expected_rows = {m.group(1): row for row in expected if (m := key.match(row))}
    for item in sorted(expected_rows.keys() - actual_rows.keys(), key=number_of):
        problems.append(f"{path}: row of {item} is missing {flag}")
    for item in sorted(actual_rows.keys() - expected_rows.keys(), key=number_of):
        problems.append(f"{path}: row of {item} should not be there {flag}")
    for item in sorted(expected_rows.keys() & actual_rows.keys(), key=number_of):
        if expected_rows[item] != actual_rows[item]:
            problems.append(f"{path}: row of {item} differs from the source {flag}")
    if not problems:
        problems.append(f"{path}: block `{name}` differs (order or header) {flag}")
    return problems


# --- The active index ----------------------------------------------------------------


def _rank(task: Task) -> tuple[int, int]:
    priority = PRIORITIES.index(task.priority) if task.priority in PRIORITIES else len(PRIORITIES)
    return priority, task.number


def order_active(tasks: list[Task]) -> tuple[list[Task], list[str]]:
    """Active tasks in dependency layers, each layer by priority and then number.

    A task never stands above what it stands on. A dependency on a closed task is
    ignored — what is finished blocks nobody.
    """
    active = {task.id: task for task in tasks if not task.closed}
    pending = {
        task_id: {dep for dep in task.depends_on if dep in active}
        for task_id, task in active.items()
    }
    ordered: list[Task] = []
    while pending:
        layer = [task_id for task_id, deps in pending.items() if not deps]
        if not layer:
            break
        layer.sort(key=lambda task_id: _rank(active[task_id]))
        ordered += [active[task_id] for task_id in layer]
        for task_id in layer:
            del pending[task_id]
        for deps in pending.values():
            deps.difference_update(layer)
    problems = []
    if pending:
        cycle = ", ".join(sorted(pending, key=number_of))
        problems.append(f"`depends_on:` forms a cycle among {cycle}")
        ordered += sorted((active[task_id] for task_id in pending), key=lambda t: t.number)
    return ordered, problems


def dependency_problems(tasks: list[Task]) -> list[str]:
    known = {task.id for task in tasks}
    problems = []
    for task in tasks:
        for dep in task.depends_on:
            if dep not in known:
                problems.append(f"{task.path}: `depends_on:` names {dep}, which has no file")
            if dep == task.id:
                problems.append(f"{task.path}: `depends_on:` names the task itself")
    return problems + order_active(tasks)[1]


def index_lines(tasks: list[Task]) -> list[str]:
    columns = (LABELS["id"], LABELS["task"], LABELS["priority"], LABELS["status"])
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for task in order_active(tasks)[0]:
        status = f"{STATUS_ICONS[task.status]} {task.status}"
        if task.status_note:
            status += f" — {task.status_note}"
        href = _href(task, BACKLOG_DIR)
        lines.append(
            f"| {task.id} | [{cell(task.title)}]({href}) | {task.priority} | {cell(status)} |"
        )
    return lines


# --- The register --------------------------------------------------------------------

REGISTER_COLUMNS = ("id", "priority", "status", "parent", "depends_on", "uc", "path", "title")


def register_text(tasks: list[Task]) -> str:
    def flat(value: str) -> str:
        return re.sub(r"[\t\r\n]+", " ", value).strip()

    rows = ["\t".join(REGISTER_COLUMNS)]
    for task in tasks:
        rows.append(
            "\t".join(
                flat(value)
                for value in (
                    task.id,
                    task.priority,
                    task.status,
                    task.parent or NONE_VALUE,
                    ", ".join(task.depends_on) or NONE_VALUE,
                    ", ".join(task.uc) or NONE_VALUE,
                    task.path,
                    task.title,
                )
            )
        )
    return "\n".join(rows) + "\n"


# --- The archive ---------------------------------------------------------------------

ARCHIVE_ROW_RE = re.compile(r"^\|\s*(BL-\d+)\s*\|")


def archive_header() -> list[str]:
    columns = (LABELS["id"], LABELS["task"], LABELS["delivered_on"])
    return ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]


def archive_row(task: Task, today: date) -> str:
    """One row, written once when the task closes. The prose is the task's own."""
    outcome = task.result_note if task.status == "DONE" else f"{task.status} — {task.result_note}"
    href = _href(task, BACKLOG_DIR)
    return f"| {task.id} | [{cell(task.title)}]({href}) | {today.isoformat()} — {cell(outcome)} |"


def archived_ids(text: str) -> list[str]:
    match = generated_block(text, "archive")
    if not match:
        return []
    return [m.group(1) for row in match.group(2).splitlines() if (m := ARCHIVE_ROW_RE.match(row))]


def archive_problems(tasks: list[Task], text: str) -> list[str]:
    if not generated_block(text, "archive"):
        return [f"{ARCHIVE_FILE}: generated block `archive` is missing its markers"]
    rows = archived_ids(text)
    by_id = {task.id: task for task in tasks}
    problems = []
    for task in tasks:
        if not task.closed or task.id in rows:
            continue
        if task.result_note.strip():
            problems.append(
                f"{ARCHIVE_FILE}: {task.id} is {task.status} but has no row (--rebuild-archive)"
            )
        else:
            #: The one gap the flag cannot fill — it would have to invent the prose.
            problems.append(
                f"{task.path}: status is {task.status} but `result_note:` is missing — "
                "write the sentence about the outcome into the task file"
            )
    for task_id in rows:
        task = by_id.get(task_id)
        if task is None:
            problems.append(f"{ARCHIVE_FILE}: row of {task_id}, which has no task file")
        elif not task.closed:
            problems.append(f"{ARCHIVE_FILE}: row of {task_id}, which is active again")
    for task_id in sorted({t for t in rows if rows.count(t) > 1}, key=number_of):
        problems.append(f"{ARCHIVE_FILE}: {task_id} has more than one row")
    return problems


def rebuilt_archive(tasks: list[Task], text: str, today: date) -> str | None:
    """Appends the missing rows, newest on top; existing rows are never rewritten."""
    match = generated_block(text, "archive")
    if not match:
        return None
    present = set(archived_ids(text))
    old_rows = [row for row in match.group(2).splitlines() if ARCHIVE_ROW_RE.match(row)]
    new_rows = [
        archive_row(task, today)
        for task in sorted(tasks, key=lambda t: -t.number)
        if task.closed and task.id not in present and task.result_note.strip()
    ]
    return replace_block(text, "archive", archive_header() + new_rows + old_rows)


# --- Requirements and use cases ------------------------------------------------------


def derived_state(tasks: list[Task]) -> str:
    """One vocabulary for requirements and use cases, derived from the claiming tasks.

    `delivered` means every claiming task is DONE — not that the acceptance holds.
    That is confirmed by a person against the prose, never by the queue.
    """
    live = [task for task in tasks if task.status != "OBSOLETE"]
    if live and all(task.status == "DONE" for task in live):
        return LABELS["delivered"]
    if any(task.status != "NEW" for task in live):
        return LABELS["in_progress"]
    return LABELS["not_started"]


@dataclass(frozen=True)
class Requirement:
    id: str
    title: str
    path: str


def load_requirements(root: Path) -> list[Requirement]:
    directory = root / REQUIREMENTS_DIR
    found = []
    for path in sorted(directory.glob("RQ-*.md")) if directory.is_dir() else ():
        match = RQ_NAME_RE.match(path.name)
        if not match:
            continue
        heading = next(
            (
                line[2:].strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.startswith("# ")
            ),
            match.group(1),
        )
        found.append(Requirement(match.group(1), heading, path.relative_to(root).as_posix()))
    return sorted(found, key=lambda rq: number_of(rq.id))


def requirements_lines(tasks: list[Task], requirements: list[Requirement]) -> list[str]:
    columns = (
        LABELS["id"],
        LABELS["requirement"],
        LABELS["state"],
        LABELS["done"],
        LABELS["items"],
    )
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    base = Path(REQUIREMENTS_FILE).parent.as_posix()
    for rq in requirements:
        items = [task for task in tasks if task.parent == rq.id and task.status != "OBSOLETE"]
        done = sum(task.status == "DONE" for task in items)
        links = ", ".join(f"[{task.id}]({_href(task, base)})" for task in items) or NONE_VALUE
        href = os.path.relpath(rq.path, base).replace("\\", "/")
        lines.append(
            f"| [{rq.id}]({href}) | {cell(rq.title)} | {derived_state(items)} | "
            f"{done}/{len(items)} | {links} |"
        )
    return lines


UC_ROW_RE = re.compile(r"^\|\s*(UC-\d+)\s*\|")


def _cells(row: str) -> list[str]:
    return [part.strip() for part in row.strip().strip("|").split("|")]


def catalogue_rows(text: str) -> list[tuple[int, str, list[str], int, int | None]]:
    """`(line index, UC id, cells, state column, wave column)` of every catalog row.

    The columns are found by the header of each table, so a table may reorder them;
    a table without a State column is not part of the catalog.
    """
    rows, state_col, wave_col = [], None, None
    for index, line in enumerate(text.splitlines()):
        if not line.startswith("|"):
            state_col = wave_col = None  # a table ends at the first line that is not a row
            continue
        cells = _cells(line)
        if cells and cells[0] == LABELS["id"]:
            state_col = cells.index(LABELS["state"]) if LABELS["state"] in cells else None
            wave_col = cells.index(LABELS["wave"]) if LABELS["wave"] in cells else None
            continue
        match = UC_ROW_RE.match(line)
        if match and state_col is not None:
            rows.append((index, match.group(1), cells, state_col, wave_col))
    return rows


def uc_state(uc_id: str, wave: str | None, tasks: list[Task]) -> str:
    if wave is not None and wave == LABELS["cancelled"]:
        return LABELS["cancelled"]
    return derived_state([task for task in tasks if uc_id in task.uc])


def rebuilt_catalogue(text: str, tasks: list[Task]) -> str:
    lines = text.splitlines(keepends=True)
    for index, uc_id, cells, state_col, wave_col in catalogue_rows(text):
        wave = cells[wave_col] if wave_col is not None else None
        cells[state_col] = uc_state(uc_id, wave, tasks)
        ending = "\n" if lines[index].endswith("\n") else ""
        lines[index] = "| " + " | ".join(cells) + " |" + ending
    fresh = "".join(lines)
    return replace_block(fresh, "uc-backlog", uc_backlog_lines(tasks)) or fresh


def uc_backlog_lines(tasks: list[Task]) -> list[str]:
    columns = (LABELS["task"], LABELS["task_status"], LABELS["uc"])
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    base = Path(CATALOGUE_FILE).parent.as_posix()
    for task in tasks:
        if task.uc:
            lines.append(
                f"| [{task.id}]({_href(task, base)}) | {task.status} | {', '.join(task.uc)} |"
            )
    return lines


def catalogue_problems(text: str, tasks: list[Task]) -> list[str]:
    problems = []
    rows = catalogue_rows(text)
    ids = [uc_id for _, uc_id, *_ in rows]
    for uc_id in sorted({uc for uc in ids if ids.count(uc) > 1}, key=number_of):
        problems.append(f"{CATALOGUE_FILE}: duplicate UC id `{uc_id}`")
    known = set(ids)
    for task in tasks:
        for uc_id in task.uc:
            if uc_id not in known:
                problems.append(
                    f"{task.path}: `uc:` names {uc_id}, which the catalog does not have"
                )
    for _, uc_id, cells, state_col, wave_col in rows:
        wave = cells[wave_col] if wave_col is not None else None
        if cells[state_col] != uc_state(uc_id, wave, tasks):
            problems.append(
                f"{CATALOGUE_FILE}: State of {uc_id} differs from the backlog (--rebuild-uc)"
            )
        if wave == LABELS["cancelled"]:
            for task in tasks:
                if uc_id in task.uc and task.status == "DONE":
                    problems.append(f"{task.path}: a DONE task claims the cancelled {uc_id}")
    if not generated_block(text, "uc-backlog"):
        problems.append(f"{CATALOGUE_FILE}: generated block `uc-backlog` is missing its markers")
    else:
        problems += _block_differences(
            CATALOGUE_FILE, "uc-backlog", text, uc_backlog_lines(tasks), "(--rebuild-uc)"
        )
    return problems


# --- Files, links and documents ------------------------------------------------------


def _is_nested_checkout(directory: Path) -> bool:
    """A git worktree, clone or submodule below the root is another repository's state."""
    try:
        return (directory / ".git").exists()
    except OSError:
        return True


def repository_files(root: Path, pattern: str = "*", base: Path | None = None) -> list[Path]:
    """Files of THIS checkout matching `pattern`.

    Agents leave worktrees under `.claude/worktrees/`: a full copy of the repository
    in an older state. A task just moved into `done/` still lies there under its old
    path, so walking into them would make the link repair choose a stale copy.
    """
    found = []
    for directory, subdirectories, files in os.walk(base or root):
        here = Path(directory)
        subdirectories[:] = [
            name
            for name in subdirectories
            if name not in IGNORED_DIRS and not _is_nested_checkout(here / name)
        ]
        found += [here / name for name in files if fnmatch.fnmatchcase(name, pattern)]
    return sorted(found)


LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
FILE_LINK_RE = re.compile(r"\]\(([^)\s#]+\.(?:md|py|yml|yaml|toml|sh|css|html|json))(#[^)\s]*)?\)")
#: Placeholders in templates are meant to be replaced, not resolved.
PLACEHOLDER_LINK_RE = re.compile(r"<[^>]+>|BL-XX|RQ-XX|UC-XX|\{\{")
FENCE_RE = re.compile(r"^(```|~~~).*?^\1", re.M | re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def _prose(text: str) -> str:
    """The text without code — an example link in a code block is not a link."""
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))


def link_problems(root: Path) -> list[str]:
    problems = []
    for path in repository_files(root, "*.md"):
        rel = path.relative_to(root).as_posix()
        for target in LINK_RE.findall(_prose(path.read_text(encoding="utf-8"))):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if PLACEHOLDER_LINK_RE.search(target):
                continue
            if "\\" in target:
                problems.append(f"{rel}: link `{target}` uses a Windows separator")
                continue
            if not (path.parent / target.split("#")[0]).resolve().exists():
                problems.append(f"{rel}: link to a missing file `{target}`")
    return problems


def fix_links(root: Path) -> list[str]:
    """Points links at where their file actually is, when exactly one candidate exists.

    Moving a task into `done/` breaks the links to it and the links it carries (one
    directory deeper now). Only unambiguous cases are rewritten; guessing between two
    files of the same name would be worse than reporting it.
    """
    changes = []

    def rewrite(match: re.Match, path: Path) -> str:
        target, anchor = match.group(1), match.group(2) or ""
        if PLACEHOLDER_LINK_RE.search(target) or (path.parent / target).resolve().exists():
            return match.group(0)
        candidates = repository_files(root, target.rsplit("/", 1)[-1])
        tail = target.lstrip("./")
        exact = [c for c in candidates if c.relative_to(root).as_posix().endswith(tail)]
        chosen = exact or candidates
        if len(chosen) != 1:
            return match.group(0)
        fresh = os.path.relpath(chosen[0], path.parent).replace("\\", "/")
        changes.append(f"{path.relative_to(root).as_posix()}: {target} → {fresh}")
        return f"]({fresh}{anchor})"

    for path in repository_files(root, "*.md"):
        text = path.read_text(encoding="utf-8")
        fresh = FILE_LINK_RE.sub(lambda match, path=path: rewrite(match, path), text)
        if fresh != text:
            path.write_text(fresh, encoding="utf-8")
    return changes


def document_problems(root: Path) -> list[str]:
    """Every document declares its responsibility and the map routes to it."""
    docs = root / "docs"
    if not docs.is_dir():
        return []
    problems = []
    index = root / DOC_MAP
    mapped = set()
    if index.exists():
        for target in LINK_RE.findall(_prose(index.read_text(encoding="utf-8"))):
            mapped.add((index.parent / target.split("#")[0]).resolve())
    for path in repository_files(root, "*.md", base=docs):
        rel = path.relative_to(root).as_posix()
        if "> **Status:**" not in path.read_text(encoding="utf-8"):
            problems.append(f"{rel}: header block (> **Status:** …) is missing")
        #: Requirements are listed by their own generated page, templates are not documents.
        exempt = (
            path == index or path.name == "_TEMPLATE.md" or rel.startswith(f"{REQUIREMENTS_DIR}/")
        )
        if not exempt and path.resolve() not in mapped:
            problems.append(f"{rel}: not linked from {DOC_MAP} (map over search)")
    return problems


#: Leftovers of initialisation. Spelled so that this file does not match itself.
LEFTOVER_RE = re.compile(r"\{\{[A-Z][A-Z_]*\}\}|kit:" + r"(?:if|endif|file)\b")
LEFTOVER_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".toml", ".txt", ".tsv", ".cfg", ".sh"}


def leftover_problems(root: Path) -> list[str]:
    problems = []
    for path in repository_files(root):
        if path.suffix not in LEFTOVER_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in LEFTOVER_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            problems.append(
                f"{path.relative_to(root).as_posix()}:{line}: "
                f"`{match.group(0)}` left over from init"
            )
    return problems


# --- GitHub --------------------------------------------------------------------------


def _run(args: tuple[str, ...], root: Path) -> tuple[str | None, str]:
    """Output of a command, or the reason why there is none — never an exception."""
    if shutil.which(args[0]) is None:
        return None, f"`{args[0]}` is not installed"
    try:
        done = subprocess.run(
            args, capture_output=True, text=True, timeout=GH_TIMEOUT_SECONDS, cwd=root
        )
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"`{' '.join(args[:3])}` did not run ({error})"
    if done.returncode != 0:
        first = next((row for row in done.stderr.splitlines() if row.strip()), "no message")
        return None, f"`{' '.join(args[:3])}` failed ({first})"
    return done.stdout, ""


def issue_problems(root: Path, tasks: list[Task]) -> tuple[list[str], list[str]]:
    """`(problems, notes)` — an active task has an open issue; a closed one has not.

    An open issue without a task file is not drift: a bug lives as an issue alone
    until it needs a written design. The direction `closed ⇒ issue closed` holds only
    on the main line — on a branch the task is moved before the merge closes the issue,
    and a guard red on every finished pull request teaches people to ignore it.
    Not having looked is said out loud: a check nobody ran must not read as passed.
    """
    raw, reason = _run(GH_ISSUE_LIST, root)
    if raw is None:
        return [], [f"task ↔ issue not checked — {reason}"]
    try:
        open_numbers = {int(row["number"]) for row in json.loads(raw or "[]")}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return [], ["task ↔ issue not checked — `gh issue list` returned no usable JSON"]
    branch, reason = _run(("git", "rev-parse", "--abbrev-ref", "HEAD"), root)
    main_line = branch is not None and branch.strip() == MAIN_BRANCH
    notes = (
        []
        if main_line
        else [
            "closed tasks not checked against issues — "
            + (reason or f"not on `{MAIN_BRANCH}`; the merge closes them")
        ]
    )
    problems = []
    for task in tasks:
        if task.number < SERIES_FIRST_NUMBER:
            continue
        if task.in_done and task.number in open_numbers and main_line:
            problems.append(f"{task.path}: the task is closed but issue #{task.number} is open")
        elif not task.in_done and task.number not in open_numbers:
            problems.append(f"{task.path}: active task has no open issue #{task.number}")
    return problems, notes


# --- Orchestration -------------------------------------------------------------------


def _read(root: Path, rel: str) -> str | None:
    path = root / rel
    return path.read_text(encoding="utf-8") if path.exists() else None


def _write(root: Path, rel: str, text: str | None, changed: list[str]) -> None:
    if text is None:
        return
    path = root / rel
    if path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
        changed.append(rel)


def rebuild(root: Path, tasks: list[Task], args: argparse.Namespace, today: date) -> list[str]:
    changed: list[str] = []
    if args.rebuild_backlog and (text := _read(root, INDEX_FILE)) is not None:
        _write(root, INDEX_FILE, replace_block(text, "active-tasks", index_lines(tasks)), changed)
    if args.rebuild_tasks:
        path = root / REGISTER_FILE
        if not path.exists() or path.read_text(encoding="utf-8") != register_text(tasks):
            path.write_text(register_text(tasks), encoding="utf-8")
            changed.append(REGISTER_FILE)
    if args.rebuild_archive and (text := _read(root, ARCHIVE_FILE)) is not None:
        _write(root, ARCHIVE_FILE, rebuilt_archive(tasks, text, today), changed)
    if REQUIREMENTS_LAYER:
        if args.rebuild_requirements and (text := _read(root, REQUIREMENTS_FILE)) is not None:
            lines = requirements_lines(tasks, load_requirements(root))
            _write(root, REQUIREMENTS_FILE, replace_block(text, "requirements", lines), changed)
        if args.rebuild_uc and (text := _read(root, CATALOGUE_FILE)) is not None:
            _write(root, CATALOGUE_FILE, rebuilt_catalogue(text, tasks), changed)
    return changed


def check(root: Path, *, with_issues: bool = True) -> tuple[list[str], list[str]]:
    """Every violation and every note about what was not checked."""
    problems, notes = [], []
    required = REQUIRED_PATHS + (REQUIRED_PATHS_REQUIREMENTS if REQUIREMENTS_LAYER else [])
    problems += [
        f"required path is missing: {rel}" for rel in required if not (root / rel).exists()
    ]

    tasks, found = load_tasks(root)
    problems += found + dependency_problems(tasks)

    if (text := _read(root, INDEX_FILE)) is not None:
        problems += _block_differences(
            INDEX_FILE, "active-tasks", text, index_lines(tasks), "(--rebuild-backlog)"
        )
    if (text := _read(root, REGISTER_FILE)) is not None and text != register_text(tasks):
        problems.append(f"{REGISTER_FILE}: differs from the task files (--rebuild-tasks)")
    if (text := _read(root, ARCHIVE_FILE)) is not None:
        problems += archive_problems(tasks, text)

    if REQUIREMENTS_LAYER:
        requirements = load_requirements(root)
        known_rq = {rq.id for rq in requirements}
        for task in tasks:
            if task.parent != NONE_VALUE and task.parent and task.parent not in known_rq:
                problems.append(
                    f"{task.path}: `parent:` names {task.parent}, which has no prose file"
                )
        if (text := _read(root, REQUIREMENTS_FILE)) is not None:
            problems += _block_differences(
                REQUIREMENTS_FILE,
                "requirements",
                text,
                requirements_lines(tasks, requirements),
                "(--rebuild-requirements)",
            )
        if (text := _read(root, CATALOGUE_FILE)) is not None:
            problems += catalogue_problems(text, tasks)

    problems += link_problems(root) + document_problems(root) + leftover_problems(root)
    if with_issues:
        found, said = issue_problems(root, tasks)
        problems += found
        notes += said
    return problems, notes


def main(argv: list[str] | None = None, root: Path = ROOT, today: date | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fix-links", action="store_true", help="repair unambiguous broken links")
    parser.add_argument(
        "--rebuild-backlog", action="store_true", help="active-tasks block of BACKLOG.md"
    )
    parser.add_argument("--rebuild-tasks", action="store_true", help="backlog/tasks.tsv")
    parser.add_argument("--rebuild-archive", action="store_true", help="append rows to DONE.md")
    parser.add_argument("--rebuild-requirements", action="store_true", help="docs/requirements.md")
    parser.add_argument(
        "--rebuild-uc", action="store_true", help="State column of docs/use-cases.md"
    )
    parser.add_argument("--rebuild-all", action="store_true", help="--fix-links and every rebuild")
    parser.add_argument("--no-issues", action="store_true", help="skip the GitHub issue check")
    args = parser.parse_args(argv)
    if args.rebuild_all:
        for flag in (
            "fix_links",
            "rebuild_backlog",
            "rebuild_tasks",
            "rebuild_archive",
            "rebuild_requirements",
            "rebuild_uc",
        ):
            setattr(args, flag, True)

    if args.fix_links:
        for change in fix_links(root):
            print(f"check_repo: link {change}")
    tasks, _ = load_tasks(root)
    for rel in rebuild(root, tasks, args, today or date.today()):
        print(f"check_repo: rewrote {rel}")

    problems, notes = check(root, with_issues=not args.no_issues)
    for note in notes:
        print(f"check_repo: {note}")
    if problems:
        for problem in problems:
            print(f"  ✗ {problem}", file=sys.stderr)
        print(f"check_repo: {len(problems)} violation(s)", file=sys.stderr)
        return 1
    print("check_repo: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
