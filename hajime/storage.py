"""JSON persistence for tasks and today's accumulated focus time."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def _clean_tasks(values) -> list[dict]:
    if not isinstance(values, list):
        return []
    tasks = []
    for value in values:
        if not isinstance(value, dict):
            continue
        title = str(value.get("title", "")).strip()
        if title:
            tasks.append({"title": title, "done": bool(value.get("done", False))})
    return tasks


def load_data(path: Path) -> tuple[list[dict], dict]:
    """Load app data, retaining compatibility with the original task-list format."""
    today = date.today().isoformat()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], {"date": today, "seconds": 0}

    if isinstance(data, list):  # Legacy format: tasks were stored at the root.
        return _clean_tasks(data), {"date": today, "seconds": 0}
    if not isinstance(data, dict):
        return [], {"date": today, "seconds": 0}

    tasks = _clean_tasks(data.get("tasks", []))
    study = data.get("study", {})
    if not isinstance(study, dict) or study.get("date") != today:
        return tasks, {"date": today, "seconds": 0}
    try:
        seconds = max(0, int(study.get("seconds", 0)))
    except (ValueError, TypeError):
        seconds = 0
    return tasks, {"date": today, "seconds": seconds}


def save_data(path: Path, tasks: list[dict], study: dict) -> None:
    """Persist tasks and study time as readable UTF-8 JSON."""
    payload = {"tasks": tasks, "study": study}
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary_path.replace(path)
