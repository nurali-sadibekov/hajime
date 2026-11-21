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
    import io, wave
    from hajime.sound import build_ringtone

    with wave.open(io.BytesIO(build_ringtone())) as wav:
        assert wav.getnframes() > 0
