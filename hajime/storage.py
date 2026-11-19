"""JSON persistence for boards, tasks and today's accumulated focus time."""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .config import MAX_BOARD_NAME, MAX_TASK_TITLE
from .models import Board, Task

APP_DIR_NAME = "Hajime"
FILE_NAME = "tasks.json"
DEFAULT_BOARD = "Tasks"
FORMAT_VERSION = 2


def default_data_path() -> Path:
    """Per-user data file; override with the ``HAJIME_DATA_FILE`` variable."""
    override = os.environ.get("HAJIME_DATA_FILE")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_DIR_NAME / FILE_NAME


def clean_board_name(name: str) -> str:
    return " ".join(name.split())[:MAX_BOARD_NAME]


@dataclass
class AppData:
    boards: list[Board] = field(default_factory=list)
    active: int = 0
    focus_day: str = field(default_factory=lambda: date.today().isoformat())
    focus_seconds: int = 0

    def __post_init__(self) -> None:
        if not self.boards:
            self.boards.append(Board(DEFAULT_BOARD))
        self.active = min(max(self.active, 0), len(self.boards) - 1)

    @property
    def board(self) -> Board:
        return self.boards[self.active]

    def roll_day(self) -> None:
        """Reset the focus counter when the calendar day changes."""
        today = date.today().isoformat()
        if self.focus_day != today:
            self.focus_day, self.focus_seconds = today, 0


def _parse_tasks(values: object) -> list[Task]:
    if not isinstance(values, list):
        return []
    tasks = []
    for value in values:
        if isinstance(value, dict):
            title = str(value.get("title", "")).strip()[:MAX_TASK_TITLE]
            if title:
                tasks.append(Task(title, bool(value.get("done", False))))
    return tasks


def _parse_boards(values: object) -> list[Board]:
    if not isinstance(values, list):
        return []
    boards = []
    for value in values:
        if isinstance(value, dict):
            name = clean_board_name(str(value.get("name", ""))) or DEFAULT_BOARD
            boards.append(Board(name, _parse_tasks(value.get("tasks"))))
    return boards


def load(path: Path) -> AppData:
    """Load data; a missing file yields defaults and a corrupt one is set aside."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return AppData()
    except (OSError, ValueError):
        _quarantine(path)
        return AppData()

    if isinstance(raw, list):  # legacy: a bare task list
        return AppData(boards=[Board(DEFAULT_BOARD, _parse_tasks(raw))])
    if not isinstance(raw, dict):
        _quarantine(path)
        return AppData()

    boards = _parse_boards(raw.get("boards"))
    if not boards and "tasks" in raw:  # v1: a single task list
        boards = [Board(DEFAULT_BOARD, _parse_tasks(raw["tasks"]))]
    try:
        active = int(raw.get("active", 0))
    except (TypeError, ValueError):
        active = 0
    data = AppData(boards=boards, active=active)

    study = raw.get("study")
    if isinstance(study, dict):
        try:
            data.focus_day = str(study.get("date", data.focus_day))
            data.focus_seconds = max(0, int(study.get("seconds", 0)))
        except (TypeError, ValueError):
            data.focus_seconds = 0
    data.roll_day()
    return data


def save(path: Path, data: AppData) -> None:
    """Atomically write data as readable UTF-8 JSON."""
    payload = {
        "version": FORMAT_VERSION,
        "active": data.active,
        "boards": [
            {"name": b.name, "tasks": [{"title": t.title, "done": t.done} for t in b.tasks]}
            for b in data.boards
        ],
        "study": {"date": data.focus_day, "seconds": data.focus_seconds},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def migrate_legacy(path: Path, legacy: Path) -> None:
    """Copy a pre-1.1 ``hajime_tasks.json`` next to the new location once."""
    if not path.exists() and legacy.is_file():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, path)
        except OSError:
            pass


def _quarantine(path: Path) -> None:
    try:
        os.replace(path, path.with_name(path.name + ".bak"))
    except OSError:
        pass
