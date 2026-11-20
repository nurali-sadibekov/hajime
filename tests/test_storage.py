import json
from datetime import date, timedelta

from hajime import storage
from hajime.models import Board, Task


def test_roundtrip(tmp_path):
    path = tmp_path / "sub" / "tasks.json"
    data = storage.AppData(
        boards=[Board("Study", [Task("ünï", True), Task("b")]), Board("Judo")],
        active=1, history={date.today().isoformat(): 90, "2024-03-05": 600},
    )
    storage.save(path, data)
    loaded = storage.load(path)
    assert loaded.boards == data.boards
    assert loaded.active == 1
    assert loaded.focus_seconds == 90
    assert loaded.history["2024-03-05"] == 600


def test_missing_file_gives_defaults(tmp_path):
    assert storage.load(tmp_path / "none.json").board.tasks == []


def test_corrupt_file_is_quarantined(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text("{not json", encoding="utf-8")
    assert storage.load(path).board.tasks == []
    assert (tmp_path / "tasks.json.bak").exists()


def test_legacy_list_and_junk_entries(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps([{"title": " x "}, {"title": ""}, 5, "y"]), encoding="utf-8")
    assert storage.load(path).board.tasks == [Task("x")]


def test_legacy_study_field_is_kept_in_history(tmp_path):
    path = tmp_path / "tasks.json"
    old = (date.today() - timedelta(days=1)).isoformat()
    path.write_text(json.dumps({"tasks": [], "study": {"date": old, "seconds": 500}}),
                    encoding="utf-8")
    data = storage.load(path)
    assert data.history == {old: 500}
    assert data.focus_seconds == 0


def test_bad_history_values_are_ignored(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"history": {"nope": 5, "2024-01-01": "x", "2024-01-02": 7,
                                            "2024-01-03": -4},
                                "study": {"date": date.today().isoformat(), "seconds": "x"}}),
                    encoding="utf-8")
    data = storage.load(path)
    assert data.history == {"2024-01-02": 7}
    assert data.focus_seconds == 0


def test_add_focus_accumulates_today():
    data = storage.AppData()
    data.add_focus(30)
    data.add_focus(0)
    data.add_focus(15)
    assert data.focus_seconds == 45


def test_migrate_legacy(tmp_path):
    legacy, new = tmp_path / "old.json", tmp_path / "d" / "new.json"
    legacy.write_text("[]", encoding="utf-8")
    storage.migrate_legacy(new, legacy)
    assert new.exists()


def test_v1_format_becomes_single_board(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"tasks": [{"title": "x", "done": True}]}), encoding="utf-8")
    data = storage.load(path)
    assert len(data.boards) == 1
    assert data.board.tasks == [Task("x", True)]


def test_active_index_is_clamped_and_boards_never_empty(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"boards": [], "active": 9}), encoding="utf-8")
    data = storage.load(path)
    assert len(data.boards) == 1 and data.active == 0
    path.write_text(json.dumps({"boards": [{"name": "  A   b "}], "active": 9}),
                    encoding="utf-8")
    data = storage.load(path)
    assert data.board.name == "A b" and data.active == 0
