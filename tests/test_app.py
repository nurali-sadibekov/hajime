"""GUI smoke tests; skipped automatically when no display is available."""

import time
import tkinter as tk

import pytest

from hajime import storage
from hajime.models import BREAK, WORK


@pytest.fixture
def app(tmp_path):
    from hajime.app import HajimeApp

    try:
        instance = HajimeApp(tmp_path / "tasks.json")
    except tk.TclError:
        pytest.skip("no display available")
    instance.update()
    yield instance
    if instance.winfo_exists():
        instance.destroy()


def test_task_lifecycle_persists(app, tmp_path):
    for title in ("one", "two"):
        app.entry.insert(0, title)
        app.add_task()
    app.toggle_task(0)
    app.delete_task(1)
    app.update()
    saved = storage.load(tmp_path / "tasks.json")
    assert [(t.title, t.done) for t in saved.board.tasks] == [("one", True)]


def test_boards_are_independent(app, monkeypatch):
    monkeypatch.setattr("hajime.app.messagebox.askyesno", lambda *a, **k: True)
    app._board_edit = -1
    app.refresh_boards()
    entry = next(w for w in app.board_list.winfo_children() if w.winfo_class() == "Entry"
                 or w.__class__.__name__ == "CTkEntry")
    entry.insert(0, "Judo")
    app._end_board_edit(-1, entry, True)
    app.update()
    app.update()
    assert [b.name for b in app.data.boards] == ["Tasks", "Judo"]
    app.entry.insert(0, "uchi komi")
    app.add_task()
    app.select_board(0)
    assert app.tasks == []
    app._delete_board(1)
    assert len(app.data.boards) == 1


def test_cannot_delete_last_board(app):
    app._delete_board(0)
    assert len(app.data.boards) == 1


def test_mode_switch(app):
    app._on_mode_selected("Break")
    assert app.timer.mode == BREAK
    assert app.mode_switch.get() == "Break"
    app._on_mode_selected("Work")
    assert app.timer.mode == WORK


def test_long_titles_are_truncated(app):
    app.entry.insert(0, "x" * 500)
    app.add_task()
    assert len(app.tasks[0].title) == 200


def test_stats_panel_overlays_and_follows_history(app):
    app.data.history["2025-06-01"] = 3600
    app.show_stats()
    app.update()
    panel = app.stats_panel
    assert panel.visible
    assert panel.year == 2026 and panel.prev_button.cget("state") == "normal"
    panel.set_year(2025)
    assert panel.total_label.cget("text").startswith("1h 0m")
    app.show_stats()  # reuses the same panel
    assert app.stats_panel is panel
    panel.hide()
    assert not panel.visible


def test_floating_timer_is_topmost_and_synced(app):
    app.toggle_mini()
    for _ in range(30):  # CTkToplevel finishes its own setup via after() callbacks
        app.update()
        time.sleep(0.01)
    assert app.mini.visible and app.mini.attributes("-topmost")
    app.toggle_timer()
    assert app.mini.button.cget("text") == "Pause"
    app.toggle_mini()
    assert not app.mini.visible


def test_ringtone_is_valid_wav():
    import io
    import wave

    from hajime.sound import build_ringtone

    with wave.open(io.BytesIO(build_ringtone())) as wav:
        assert wav.getnframes() > 0


def test_remote_copy_replaces_boards_but_keeps_view_and_merges_history(app, tmp_path):
    app.entry.insert(0, "local")
    app.add_task()
    app.data.history["2026-01-01"] = 600
    payload = storage.to_payload(app.data)
    payload["boards"][0]["tasks"] = [{"title": "from phone", "done": False}]
    payload["history"] = {"2026-01-01": 300, "2026-01-02": 60}
    app._apply_remote(payload)
    app.update()
    assert [t.title for t in app.tasks] == ["from phone"]
    assert app.data.history == {"2026-01-01": 600, "2026-01-02": 60}
    assert [t.title for t in storage.load(tmp_path / "tasks.json").board.tasks] == ["from phone"]


def test_signed_out_app_never_writes_placeholder_data(tmp_path, monkeypatch):
    from hajime.app import HajimeApp

    monkeypatch.setenv("HAJIME_DATA_FILE", str(tmp_path / "tasks.json"))
    monkeypatch.delenv("HAJIME_SUPABASE_URL", raising=False)
    (tmp_path / "tasks.json").write_text('{"tasks": [{"title": "real", "done": false}]}')
    try:
        instance = HajimeApp()
    except tk.TclError:
        pytest.skip("no display available")
    instance.update()
    instance._on_close()
    kept = storage.load(tmp_path / "tasks.json")
    assert [t.title for t in kept.board.tasks] == ["real"]


def test_goals_panel_behaves_like_tasks(app, tmp_path):
    app.show_goals()
    panel = app.goals_panel
    for title in ("a", "b", "c"):
        panel.entry.insert(0, title)
        panel.add_goal()
    panel.set_year(panel.year + 1)
    panel.entry.insert(0, "next year")
    panel.add_goal()
    panel.set_year(panel.year - 1)
    app.update()

    # rename (click -> edit -> Return)
    panel._begin_edit(0)
    app.update()
    entry = panel.rows.frames[0].winfo_children()[1]
    entry.delete(0, "end")
    entry.insert(0, "renamed")
    panel._end_edit(0, entry, True)
    app.update()

    # reorder (drag the first goal onto the last row)
    panel.drag_index, panel._drag_moved = 0, True
    goals = panel._year_goals()
    goals.insert(2, goals.pop(0))
    panel._reorder(goals)
    panel.drag_index = None
    panel._changed()

    panel.toggle(0)
    assert [g.title for g in panel._year_goals()] == ["b", "c", "renamed"]
    assert panel._year_goals()[0].done
    saved = storage.load(tmp_path / "tasks.json")
    assert [g.title for g in saved.goals if g.year == panel.year] == ["b", "c", "renamed"]
    assert len(saved.goals) == 4

    panel.delete(1)
    assert [g.title for g in panel._year_goals()] == ["b", "renamed"]


def test_toggle_and_reorder_reuse_row_widgets(app):
    """Rows are updated in place (no destroy/rebuild), which is what avoids flicker."""
    for title in ("one", "two", "three"):
        app.entry.insert(0, title)
        app.add_task()
    app.update()
    frames = list(app.row_list.frames)

    app.toggle_task(1)
    app.tasks.insert(0, app.tasks.pop(2))  # what a drag step does
    app.refresh()
    app.update()

    assert app.row_list.frames == frames
    labels = [r.label.cget("text") for r in app.row_list.rows]
    assert labels == ["three", "one", "two"]
    assert [bool(r.box.get()) for r in app.row_list.rows] == [False, False, True]
