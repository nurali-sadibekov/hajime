"""JSON persistence for boards, tasks and the per-day study history."""

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
    history: dict[str, int] = field(default_factory=dict)  # ISO date -> studied seconds

    def __post_init__(self) -> None:
        if not self.boards:
            self.boards.append(Board(DEFAULT_BOARD))
        self.active = min(max(self.active, 0), len(self.boards) - 1)

    @property
    def board(self) -> Board:
        return self.boards[self.active]

    @property
    def focus_seconds(self) -> int:
        """Seconds studied today."""
        return self.history.get(date.today().isoformat(), 0)

    def add_focus(self, seconds: int) -> None:
        if seconds > 0:
            today = date.today().isoformat()
            self.history[today] = self.history.get(today, 0) + seconds


def _parse_history(values: object) -> dict[str, int]:
    if not isinstance(values, dict):
        return {}
    history = {}
    for key, value in values.items():
        try:
            day = date.fromisoformat(str(key)).isoformat()
            seconds = int(value)
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            history[day] = seconds
    return history


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
    data = AppData(boards=boards, active=active, history=_parse_history(raw.get("history")))

    study = raw.get("study")  # pre-heatmap format: only the latest day was kept
    if isinstance(study, dict):
        legacy = _parse_history({study.get("date"): study.get("seconds")})
        for day, seconds in legacy.items():
            data.history[day] = max(data.history.get(day, 0), seconds)
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
        "history": dict(sorted(data.history.items())),
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
