"""CustomTkinter user interface for Hajime (fixed 4:3 window, boards sidebar)."""

from __future__ import annotations

import logging
import queue
import secrets
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from . import cloud, storage
from .auth_screen import AuthScreen
from .belt_art import BeltIllustrations
from .config import (
    ACCENT,
    ACCENT_BREAK,
    ACCENT_HOVER,
    ACCENT_TEXT,
    ACTIVE_BG,
    BELTS,
    BG,
    BREAK_SECONDS,
    ERROR,
    FAINT,
    INK,
    INK_HOVER,
    LINE,
    MAX_BOARD_NAME,
    MAX_BOARDS,
    MAX_TASK_TITLE,
    MAX_TASKS_PER_BOARD,
    MUTED,
    ON_ACCENT,
    PANEL,
    SAVE_INTERVAL_SECONDS,
    TRACK,
    WORK_SECONDS,
)
from .fonts import build_fonts
from .goals_window import GoalsPanel
from .icons import icon
from .mini_timer import MiniTimer
from .models import BREAK, WORK, Board, Pomodoro, Task, belt_rank, completion, next_belt_goal
from .row_list import RowList
from .sound import play_ringtone
from .stats_window import StatsPanel

WINDOW_SIZE = (700, 525)  # 4:3
SIDEBAR_WIDTH = 210
TASK_WRAP = 280
LOG = logging.getLogger("hajime")
DRAG_THRESHOLD_PX = 6
MODE_LABELS = {WORK: "Work", BREAK: "Break"}
NEW_BOARD = -1  # sentinel for "the new-board name field is open"


def _card(master: tk.Misc, **pack) -> ctk.CTkFrame:
    card = ctk.CTkFrame(master, fg_color=PANEL, corner_radius=14,
                        border_width=1, border_color=LINE)
    card.pack(**pack)
    return card


class HajimeApp(ctk.CTk):
    def __init__(self, data_path: Path | None = None) -> None:
        ctk.set_appearance_mode("light")
        super().__init__(fg_color=BG)
        # An explicit ``data_path`` means plain local storage with no account.
        self._cloud_mode = data_path is None
        if data_path is None:
            self.data = storage.AppData()  # placeholder; never written to disk (see _save)
        else:
            self.data = storage.load(data_path)
        self.data_path: Path | None = data_path  # None until a session or local mode starts
        self._events: queue.Queue = queue.Queue()
        self._auth: cloud.SupabaseAuth | None = None
        self._sync: cloud.CloudSync | None = None
        self._signin_cancel: threading.Event | None = None
        self.auth_screen: AuthScreen | None = None
        self.client_id = secrets.token_hex(8)
        self.account_email = ""
        self.sync_online = True
        self._queued_seq = 0  # newest change handed to the uploader
        self.timer = Pomodoro(WORK_SECONDS, BREAK_SECONDS)
        self._timer_job: str | None = None
        self.stats_panel: StatsPanel | None = None
        self.goals_panel: GoalsPanel | None = None
        self.mini: MiniTimer | None = None
        self._last_save = time.monotonic()
        self._editing: int | None = None  # task being edited
        self._board_edit: int | None = None  # board index being renamed, or NEW_BOARD
        self._drag_index: int | None = None
        self._drag_origin_y = 0
        self._drag_moved = False
        self._drag_bindings: tuple[str, str] = ("", "")
        self._board_buttons: list[tuple[int, ctk.CTkButton]] = []

        self.title("Hajime")
        self.geometry(f"{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}")
        self.resizable(False, False)
        self.fonts = build_fonts(self)
        self.board_menu = tk.Menu(self, tearoff=0, font=self.fonts["small"])
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.refresh_boards()
        self.refresh()
        self._draw_timer()
        if self._cloud_mode:
            self._update_account()
            self._poll_events()
            self._show_auth()

    @property
    def tasks(self) -> list[Task]:
        return self.data.board.tasks

    # ----- layout ---------------------------------------------------------
    def _build(self) -> None:
        f = self.fonts
        side = ctk.CTkFrame(self, fg_color="transparent", width=SIDEBAR_WIDTH)
        side.pack(side="left", fill="y", padx=(16, 0), pady=16)
        side.pack_propagate(False)
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=16, pady=16)

        # Sidebar: brand, boards, timer
        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            brand, text="", image=icon("activity", MUTED, 16), width=30, height=30,
            corner_radius=8,
            fg_color="transparent", text_color=MUTED, hover_color=TRACK,
            command=self.show_stats).pack(side="right", padx=(2, 0))
        ctk.CTkButton(
            brand, text="", image=icon("goals", MUTED, 16), width=30, height=30,
            corner_radius=8,
            fg_color="transparent", text_color=MUTED, hover_color=TRACK,
            command=self.show_goals).pack(side="right")
        if self._cloud_mode:
            account = ctk.CTkFrame(side, fg_color="transparent")
            account.pack(side="bottom", fill="x", pady=(6, 0))
            self.account_label = ctk.CTkLabel(
                account, text="", text_color=MUTED, font=f["small"], anchor="w")
            self.account_label.pack(side="left", padx=6)
            self.account_button = ctk.CTkButton(
                account, text="Sign out", width=60, height=24, corner_radius=8, font=f["small"],
                fg_color="transparent", text_color=MUTED, hover_color=TRACK,
                command=self._account_action)
            self.account_button.pack(side="right")
        timer = _card(side, side="bottom", fill="x", pady=(10, 0))
        self.mode_switch = ctk.CTkSegmentedButton(
            timer, values=list(MODE_LABELS.values()), command=self._on_mode_selected,
            height=26, corner_radius=8, font=f["small"], fg_color=TRACK, selected_color=PANEL,
            selected_hover_color=PANEL, unselected_color=TRACK, unselected_hover_color=LINE,
            text_color=INK)
        self.mode_switch.pack(fill="x", padx=12, pady=(12, 0))
        self.clock_label = ctk.CTkLabel(timer, text="", text_color=INK, font=f["title"])
        self.clock_label.pack(pady=(4, 0))
        buttons = ctk.CTkFrame(timer, fg_color="transparent")
        buttons.pack(padx=12, pady=(2, 0))
        self.timer_button = ctk.CTkButton(
            buttons, text="Start", width=76, height=32, corner_radius=9, font=f["button"],
            fg_color=INK, hover_color=INK_HOVER, command=self.toggle_timer)
        self.timer_button.pack(side="left")
        ctk.CTkButton(
            buttons, text="Reset", width=50, height=32, corner_radius=9, font=f["button"],
            fg_color="transparent", text_color=MUTED, hover_color=TRACK,
            command=self.reset_timer).pack(side="left", padx=(4, 0))
        self.float_button = ctk.CTkButton(
            buttons, text="", image=icon("pip", MUTED, 16), width=32, height=32,
            corner_radius=9,
            fg_color="transparent", text_color=MUTED, hover_color=TRACK,
            command=self.toggle_mini)
        self.float_button.pack(side="left", padx=(4, 0))
        self.focus_label = ctk.CTkLabel(timer, text="", text_color=MUTED, font=f["small"])
        self.focus_label.pack(pady=(2, 8))

        ctk.CTkButton(
            side, text=" Board", image=icon("plus", MUTED, 14), compound="left", height=32,
            corner_radius=9, font=f["button"], anchor="w",
            fg_color="transparent", text_color=MUTED, hover_color=TRACK,
            command=self._start_new_board).pack(side="bottom", fill="x", pady=(6, 0))
        self.board_list = ctk.CTkScrollableFrame(
            side, fg_color=PANEL, corner_radius=14, border_width=1, border_color=LINE,
            scrollbar_button_color=LINE, scrollbar_button_hover_color=FAINT)
        self.board_list.pack(fill="both", expand=True)

        # Main: header card, add field, task list
        card = _card(main, fill="x", pady=(0, 10))
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(12, 0))
        names = ctk.CTkFrame(top, fg_color="transparent")
        names.pack(side="left", fill="x", expand=True)
        self.board_label = ctk.CTkLabel(names, text="", text_color=MUTED, font=f["small"],
                                        anchor="w")
        self.board_label.pack(anchor="w")
        self.rank_label = ctk.CTkLabel(names, text="", text_color=INK, font=f["title"],
                                       anchor="w")
        self.rank_label.pack(anchor="w")
        self.belt_canvas = tk.Canvas(top, width=150, height=58, bg=PANEL, highlightthickness=0)
        self.belt_canvas.pack(side="right")
        self.belt_art = BeltIllustrations(self.belt_canvas)
        self.progress = ctk.CTkProgressBar(card, height=7, fg_color=TRACK, progress_color=ACCENT)
        self.progress.pack(fill="x", padx=18, pady=(8, 4))
        self.percent_label = ctk.CTkLabel(card, text="", text_color=MUTED, font=f["small"])
        self.percent_label.pack(anchor="w", padx=18, pady=(0, 0))
        goal_row = ctk.CTkFrame(card, fg_color="transparent")
        goal_row.pack(fill="x", padx=18, pady=(0, 10))
        self.goal_label = ctk.CTkLabel(goal_row, text="", text_color=ACCENT_TEXT, font=f["small"])
        self.goal_label.pack(side="left")
        self.goal_canvas = tk.Canvas(goal_row, width=60, height=23, bg=PANEL,
                                     highlightthickness=0)
        self.goal_canvas.pack(side="left", padx=(8, 0))
        self.goal_art = BeltIllustrations(self.goal_canvas)

        add = _card(main, fill="x", pady=(0, 10))
        self.entry = ctk.CTkEntry(
            add, placeholder_text="Add a task", font=f["body"], height=38, border_width=0,
            fg_color=PANEL, text_color=INK, placeholder_text_color=MUTED)
        self.entry.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=3)
        self.entry.bind("<Return>", lambda _e: self.add_task())
        ctk.CTkButton(
            add, text="", image=icon("plus", ON_ACCENT, 16), width=32, height=32,
            corner_radius=9, fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.add_task,
        ).pack(side="right", padx=(0, 6))

        self.task_list = ctk.CTkScrollableFrame(
            main, fg_color=PANEL, corner_radius=14, border_width=1, border_color=LINE,
            scrollbar_button_color=LINE, scrollbar_button_hover_color=FAINT)
        self.task_list.pack(fill="both", expand=True)
        self.row_list = RowList(
            self.task_list, f, TASK_WRAP, on_toggle=self.toggle_task, on_delete=self.delete_task,
            on_press=self._drag_start, on_edit_end=self._end_edit)

    # ----- boards ---------------------------------------------------------
    def refresh_boards(self) -> None:
        for child in self.board_list.winfo_children():
            child.destroy()
        self._board_buttons = []
        for index, board in enumerate(self.data.boards):
            if self._board_edit == index:
                self._board_entry(board.name, index)
                continue
            button = ctk.CTkButton(
                self.board_list, text=board.name, anchor="w", height=32, corner_radius=9,
                font=self.fonts["button"], fg_color="transparent", text_color=INK,
                hover_color=TRACK, command=lambda i=index: self.select_board(i))
            button.pack(fill="x", pady=1)
            button.bind("<Double-Button-1>", lambda _e, i=index: self._rename_board(i))
            for sequence in ("<Button-3>", "<Button-2>") if sys.platform == "darwin" \
                    else ("<Button-3>",):
                button.bind(sequence, lambda e, i=index: self._board_context(e, i))
            self._board_buttons.append((index, button))
        if self._board_edit == NEW_BOARD:
            self._board_entry("", NEW_BOARD)
        self._style_boards()

    def _board_entry(self, initial: str, index: int) -> None:
        entry = ctk.CTkEntry(self.board_list, font=self.fonts["body"], height=32,
                             border_width=1, border_color=ACCENT, fg_color=PANEL,
                             text_color=INK, placeholder_text="Board name")
        entry.pack(fill="x", pady=1)
        entry.insert(0, initial)
        entry.bind("<Return>", lambda _e: self._end_board_edit(index, entry, True))
        entry.bind("<Escape>", lambda _e: self._end_board_edit(index, entry, False))
        entry.bind("<FocusOut>", lambda _e: self._end_board_edit(index, entry, True))
        entry.focus_set()
        entry.select_range(0, "end")
        self.after_idle(self.board_list._parent_canvas.yview_moveto, 1.0)

    def _style_boards(self) -> None:
        for index, button in self._board_buttons:
            current = index == self.data.active
            button.configure(fg_color=ACTIVE_BG if current else "transparent",
                             text_color=INK,
                             hover_color=ACTIVE_BG if current else TRACK)

    def select_board(self, index: int) -> None:
        if index == self.data.active:
            return
        self.data.active = index
        self._editing = None
        self._save()
        self._style_boards()
        self.refresh()

    def _start_new_board(self) -> None:
        self._board_edit = NEW_BOARD
        self.refresh_boards()

    def _rename_board(self, index: int) -> None:
        self._board_edit = index
        self.after_idle(self.refresh_boards)

    def _end_board_edit(self, index: int, entry: ctk.CTkEntry, commit: bool) -> None:
        if self._board_edit != index:  # already handled (Return followed by FocusOut)
            return
        self._board_edit = None
        name = storage.clean_board_name(entry.get())
        if commit and name:
            if index == NEW_BOARD:
                if len(self.data.boards) >= MAX_BOARDS:
                    self.bell()
                    self.after_idle(self.refresh_boards)
                    return
                self.data.boards.append(Board(name))
                self.data.active = len(self.data.boards) - 1
                self._editing = None
            else:
                self.data.boards[index].name = name
            self._save()
        self.after_idle(self.refresh_boards)
        self.after_idle(self.refresh)

    def _board_context(self, event: tk.Event, index: int) -> None:
        menu = self.board_menu
        menu.delete(0, "end")
        menu.add_command(label="Rename", command=lambda: self._rename_board(index))
        menu.add_command(label="Duplicate", command=lambda: self._duplicate_board(index))
        menu.add_command(
            label="Delete", command=lambda: self._delete_board(index),
            state="normal" if len(self.data.boards) > 1 else "disabled")
        menu.tk_popup(event.x_root, event.y_root)

    def _duplicate_board(self, index: int) -> None:
        if len(self.data.boards) >= MAX_BOARDS:
            self.bell()
            return
        source = self.data.boards[index]
        names = {b.name for b in self.data.boards}
        suffix, n = " copy", 1
        while True:
            name = storage.clean_board_name(source.name)
            room = MAX_BOARD_NAME - len(suffix)
            name = f"{name[:room].rstrip()}{suffix}"
            if name not in names:
                break
            n += 1
            suffix = f" copy {n}"
        copy = Board(name, [Task(t.title, t.done) for t in source.tasks])
        self.data.boards.insert(index + 1, copy)
        self.data.active = index + 1
        self._editing = None
        self._save()
        self.refresh_boards()
        self.refresh()

    def _delete_board(self, index: int) -> None:
        board = self.data.boards[index]
        if len(self.data.boards) < 2:
            return
        if board.tasks and not messagebox.askyesno(
                "Delete board", f"Delete “{board.name}” and its {len(board.tasks)} tasks?",
                parent=self):
            return
        del self.data.boards[index]
        if index < self.data.active:
            self.data.active -= 1
        self.data.active = min(self.data.active, len(self.data.boards) - 1)
        self._editing = None
        self._save()
        self.refresh_boards()
        self.refresh()

    # ----- tasks ----------------------------------------------------------
    def add_task(self) -> None:
        title = self.entry.get().strip()[:MAX_TASK_TITLE]
        if not title:
            return
        if len(self.tasks) >= MAX_TASKS_PER_BOARD:
            self.bell()  # board is full
            return
        self.tasks.append(Task(title))
        self.entry.delete(0, "end")
        self._save()
        self.refresh()
        self.update_idletasks()
        self.task_list._parent_canvas.yview_moveto(1.0)

    def toggle_task(self, index: int) -> None:
        task = self.tasks[index]
        task.done = not task.done
        self._save()
        self.refresh()

    def delete_task(self, index: int) -> None:
        del self.tasks[index]
        self._editing = None
        self._save()
        self.refresh()

    def _begin_edit(self, index: int) -> None:
        self._editing = index
        self.refresh()

    def _end_edit(self, index: int, entry: ctk.CTkEntry, commit: bool) -> None:
        if self._editing != index:  # already handled (Return followed by FocusOut)
            return
        self._editing = None
        title = entry.get().strip()[:MAX_TASK_TITLE]
        if commit and title:
            self.tasks[index].title = title
            self._save()
        self.after_idle(self.refresh)

    def _drag_start(self, event: tk.Event, index: int) -> None:
        self._drag_index, self._drag_origin_y, self._drag_moved = index, event.y_root, False
        self._drag_bindings = (
            self.bind("<B1-Motion>", self._drag_motion, add="+"),
            self.bind("<ButtonRelease-1>", self._drag_end, add="+"),
        )

    def _drag_motion(self, event: tk.Event) -> None:
        if self._drag_index is None:
            return
        if not self._drag_moved and abs(event.y_root - self._drag_origin_y) < DRAG_THRESHOLD_PX:
            return
        self._drag_moved = True
        target = next(
            (i for i, row in enumerate(self.row_list.frames)
             if row.winfo_rooty() <= event.y_root < row.winfo_rooty() + row.winfo_height()),
            None,
        )
        if target is not None and target != self._drag_index:
            tasks = self.tasks
            tasks.insert(target, tasks.pop(self._drag_index))
            self._drag_index = target
            self.refresh()

    def _drag_end(self, _event: tk.Event) -> None:
        index, moved = self._drag_index, self._drag_moved
        self._drag_index = None
        motion, release = self._drag_bindings
        self.unbind("<B1-Motion>", motion)
        self.unbind("<ButtonRelease-1>", release)
        if index is None:
            return
        if moved:
            self._save()
            self.refresh()
        else:
            self._begin_edit(index)

    # ----- timer ----------------------------------------------------------
    def toggle_timer(self) -> None:
        if self.timer.running:
            self._credit(self.timer.pause())
            self._cancel_timer_job()
            self._save()
        else:
            self.timer.start()
            self._schedule_tick()
        self._draw_timer()

    def _on_mode_selected(self, label: str) -> None:
        mode = next(m for m, text in MODE_LABELS.items() if text == label)
        if mode != self.timer.mode:
            self._credit(self.timer.switch(mode))
            self._cancel_timer_job()
            self._save()
        self._draw_timer()

    def reset_timer(self) -> None:
        self._credit(self.timer.reset())
        self._cancel_timer_job()
        self._save()
        self._draw_timer()

    def _schedule_tick(self) -> None:
        self._timer_job = self.after(250, self._on_tick)

    def _cancel_timer_job(self) -> None:
        if self._timer_job is not None:
            self.after_cancel(self._timer_job)
            self._timer_job = None

    def _on_tick(self) -> None:
        self._timer_job = None
        earned, finished = self.timer.tick()
        self._credit(earned)
        if finished:
            self._save()
            if not play_ringtone():
                self.bell()
        elif earned and time.monotonic() - self._last_save >= SAVE_INTERVAL_SECONDS:
            self._save(upload=False)  # local only; pause/finish/quit upload, saving requests
        self._draw_timer()
        if self.timer.running:
            self._schedule_tick()

    def _credit(self, seconds: int) -> None:
        self.data.add_focus(seconds)

    def show_stats(self) -> None:
        if self.stats_panel is None:
            self.stats_panel = StatsPanel(self)
        if self.goals_panel is not None:
            self.goals_panel.hide()
        self.stats_panel.show()

    def show_goals(self) -> None:
        if self.goals_panel is None:
            self.goals_panel = GoalsPanel(self)
        if self.stats_panel is not None:
            self.stats_panel.hide()
        self.goals_panel.show()

    def toggle_mini(self) -> None:
        """Show or hide the always-on-top floating timer."""
        if self.mini is None:
            self.mini = MiniTimer(self)
        if self.mini.visible:
            self.mini.hide()
        else:
            self.mini.show()
            self.float_button.configure(image=icon("pip", INK, 16))
            self._draw_timer()

    def on_mini_hidden(self) -> None:
        self.float_button.configure(image=icon("pip", MUTED, 16))

    def _draw_timer(self) -> None:
        minutes, seconds = divmod(self.timer.remaining, 60)
        clock = f"{minutes:02d}:{seconds:02d}"
        self.clock_label.configure(
            text=clock, text_color=ACCENT_BREAK if self.timer.mode == BREAK else INK)
        self.mode_switch.set(MODE_LABELS[self.timer.mode])
        self.timer_button.configure(text="Pause" if self.timer.running else "Start")
        self.title(f"{clock} · Hajime" if self.timer.running else "Hajime")
        if self.mini is not None:
            self.mini.update_state(clock, self.timer.running, self.timer.mode == BREAK)
        hours, rest = divmod(self.data.focus_seconds, 3600)
        self.focus_label.configure(
            text=f"{hours}h {rest // 60}m today" if hours else f"{rest // 60}m today")

    # ----- rendering ------------------------------------------------------
    def refresh(self) -> None:
        """Redraw the active board: header, belt and task list."""
        tasks = self.tasks
        fraction = completion(tasks)
        rank = belt_rank(fraction)
        self.board_label.configure(text=self.data.board.name)
        self.rank_label.configure(text=f"{BELTS[rank][0]} belt")
        self.belt_art.draw(rank)
        self.progress.set(fraction)
        done = sum(t.done for t in tasks)
        self.percent_label.configure(
            text=f"{done}/{len(tasks)} done" if tasks else "No tasks yet")

        goal = next_belt_goal(tasks)
        if goal is None:
            self.goal_label.configure(text="Top belt reached. Osu!")
            self.goal_art.clear()
        else:
            belt, left = goal
            self.goal_label.configure(
                text=f"Next: {BELTS[belt][0]} belt · {left} more task{'s' * (left != 1)} to go")
            self.goal_art.draw(belt)

        self.row_list.sync(tasks, self._editing, self._drag_index if self._drag_moved else None)

    # ----- persistence / lifecycle ---------------------------------------
    def report_callback_exception(self, exc, val, tb) -> None:
        """Log UI callback errors instead of losing them on windowed launches."""
        LOG.error("Unhandled error in UI callback", exc_info=(exc, val, tb))
        self.title("Hajime · something went wrong (see hajime.log)")

    def _save(self, upload: bool = True) -> None:
        self._last_save = time.monotonic()
        if self.data_path is None:  # signed out: the placeholder must not overwrite real data
            return
        try:
            storage.save(self.data_path, self.data)
        except OSError as error:
            self.title(f"Hajime · could not save ({error.strerror or 'I/O error'})")
        if self._sync is not None and upload:
            self._mark_unsynced(True)  # survives a restart until the server has the change
            self._queued_seq = self._sync.push(storage.to_payload(self.data))
        if self.stats_panel is not None and self.stats_panel.visible:
            self.stats_panel.refresh()

    def _on_close(self) -> None:
        self._credit(self.timer.pause())
        self._save()
        if self._sync is not None and self._sync.flush():
            self._mark_unsynced(False)
        self.destroy()

    def _unsynced_marker(self) -> Path | None:
        return None if self.data_path is None else self.data_path.with_suffix(".unsynced")

    def _mark_unsynced(self, unsynced: bool) -> None:
        marker = self._unsynced_marker()
        if marker is None:
            return
        try:
            if unsynced:
                marker.touch()
            else:
                marker.unlink(missing_ok=True)
        except OSError:
            LOG.warning("could not update the unsynced marker", exc_info=True)

    # ----- account & sync -------------------------------------------------
    def _show_auth(self) -> None:
        if self.auth_screen is None:
            self.auth_screen = AuthScreen(
                self, self.fonts, self._google_clicked, self._cancel_signin, self._use_local)
        self.auth_screen.show()
        config = cloud.load_config()
        if config is None:
            self._auth = None
            self.auth_screen.idle(
                "Cloud sync isn't configured. Set HAJIME_SUPABASE_URL and "
                "HAJIME_SUPABASE_ANON_KEY (see the README).", configured=False)
            return
        if self._auth is None or self._auth.config != config:
            self._auth = cloud.SupabaseAuth(config)
        if self._auth.session or self._auth.load_saved():
            self.auth_screen.busy("Signing you in…")
            threading.Thread(target=self._restore_session, args=(self._auth,),
                             daemon=True).start()
        else:
            self.auth_screen.idle()

    def _restore_session(self, auth: cloud.SupabaseAuth) -> None:
        try:
            auth.access_token()  # renews an expired token
        except cloud.NetworkError:
            pass  # offline: carry on with the cached copy and sync later
        except cloud.CloudError:
            self._events.put(("signin_failed", "Your session expired. Please sign in again.", None))
            return
        self._events.put(("signed_in", None, None))

    def _google_clicked(self) -> None:
        auth = self._auth
        if auth is None:
            return
        cancel = self._signin_cancel = threading.Event()
        self.auth_screen.busy("Finish signing in with Google in your browser…", cancellable=True)

        def work() -> None:
            try:
                auth.sign_in_with_google(cancel)
            except cloud.CloudError as error:
                self._events.put(("signin_failed", "" if cancel.is_set() else str(error), None))
            except Exception as error:  # never leave the screen stuck on "waiting"
                LOG.exception("sign-in failed")
                self._events.put(("signin_failed", str(error), None))
            else:
                self._events.put(("signed_in", None, None))

        threading.Thread(target=work, daemon=True).start()

    def _cancel_signin(self) -> None:
        if self._signin_cancel is not None:
            self._signin_cancel.set()

    def _use_local(self) -> None:
        """Run without an account: plain local file, no sync."""
        self.data_path = storage.default_data_path()
        storage.migrate_legacy(
            self.data_path, Path(__file__).resolve().parent.parent / "hajime_tasks.json")
        self.data = storage.load(self.data_path)
        self.account_email = ""
        self._reset_views()
        self._update_account()
        self.auth_screen.hide()

    def _reset_views(self) -> None:
        self._editing = None
        self._board_edit = None
        self.refresh_boards()
        self.refresh()
        self._draw_timer()
        if self.goals_panel is not None and self.goals_panel.visible:
            self.goals_panel.refresh()

    def _on_signed_in(self) -> None:
        session = self._auth.session if self._auth else None
        if session is None:
            self._show_auth()
            return
        if self._sync is not None:
            self._sync.stop()
        self.account_email = session.email
        self.sync_online = True
        self.data_path = storage.user_data_path(session.user_id)
        legacy = storage.default_data_path()
        had_cache = self.data_path.exists()
        seeded = False
        if not had_cache:  # pick up the pre-1.1 file next to the source tree, if any
            storage.migrate_legacy(
                legacy, Path(__file__).resolve().parent.parent / "hajime_tasks.json")
        if had_cache:
            self.data = storage.load(self.data_path)
        elif legacy.is_file():  # first sign-in: adopt tasks made before accounts existed
            self.data = storage.load(legacy)
            seeded = True
        else:
            self.data = storage.AppData()
        self._reset_views()

        sync = self._sync = cloud.CloudSync(
            self._auth, self.client_id,
            lambda event, payload: self._events.put((event, payload, sync)))
        self._update_account()
        try:
            storage.save(self.data_path, self.data)
            if seeded:
                legacy.replace(legacy.with_name(legacy.name + ".imported"))
        except OSError:
            LOG.warning("could not write the local cache", exc_info=True)
        marker = self._unsynced_marker()
        sync.start(storage.to_payload(self.data), unsynced=bool(marker and marker.exists()))
        if had_cache:
            self.auth_screen.hide()
        else:  # nothing local to show yet: wait for the first pull
            self.auth_screen.busy("Syncing your boards…")

    def _account_action(self) -> None:
        if self._sync is not None:
            self._sign_out()
        else:
            self._show_auth()

    def _sign_out(self, message: str = "") -> None:
        self._credit(self.timer.pause())
        self._cancel_timer_job()
        if self._sync is not None:
            self._save()
            if self._sync.flush():
                self._mark_unsynced(False)
            self._sync = None
        if self.mini is not None and self.mini.visible:
            self.mini.hide()
        if self._auth is not None:
            self._auth.sign_out()
        self.timer = Pomodoro(WORK_SECONDS, BREAK_SECONDS)
        self.data = storage.AppData()
        self.data_path = None
        self.account_email = ""
        self._reset_views()
        self._update_account()
        self._show_auth()
        if message:
            self.auth_screen.idle(message, error=True)

    def _update_account(self) -> None:
        if self._sync is None:
            self.account_label.configure(text="Not synced", text_color=MUTED)
            self.account_button.configure(text="Sign in")
            return
        email = self.account_email
        short = email if len(email) <= 17 else email[:16] + "…"
        self.account_label.configure(
            text=short if self.sync_online else "Offline · will retry",
            text_color=MUTED if self.sync_online else ERROR)
        self.account_button.configure(text="Sign out")

    def _poll_events(self) -> None:
        try:
            while True:
                self._handle_event(*self._events.get_nowait())
        except queue.Empty:
            pass
        self.after(150, self._poll_events)

    def _handle_event(self, event: str, payload, source) -> None:
        if event == "signed_in":
            self._on_signed_in()
        elif event == "signin_failed":
            self._signin_cancel = None
            self.auth_screen.idle(payload, error=bool(payload))
        elif source is None or source is not self._sync:
            return  # stale event from a session that has since ended
        elif event == "remote":
            self._apply_remote(payload)
        elif event == "synced":
            self.auth_screen.hide()
        elif event == "pushed":
            if payload >= self._queued_seq:  # nothing newer is still waiting
                self._mark_unsynced(False)
        elif event == "status":
            self.sync_online = payload == "online"
            self._update_account()
            if not self.sync_online:
                self.auth_screen.hide()  # offline at launch: use the local copy
        elif event == "auth_lost":
            self._sign_out("Your session expired. Please sign in again.")

    def _apply_remote(self, payload: dict) -> None:
        """Adopt a copy saved by another device (this device's view settings are kept)."""
        goals = self.goals_panel
        if self._drag_index is not None or (goals is not None and goals.drag_index is not None):
            # don't reshuffle rows under the cursor
            self.after(300, self._apply_remote, payload)
            return
        remote = storage.from_payload(payload)
        if remote is None:
            return
        for day, seconds in self.data.history.items():
            remote.history[day] = max(remote.history.get(day, 0), seconds)
        current = self.data.board.name
        self.data.boards = remote.boards
        self.data.history = remote.history
        self.data.goals = remote.goals
        self.data.active = next(
            (i for i, b in enumerate(remote.boards) if b.name == current),
            min(self.data.active, len(remote.boards) - 1))
        if self.data_path is not None:
            try:
                storage.save(self.data_path, self.data)
            except OSError:
                LOG.warning("could not write the local cache", exc_info=True)
        self._reset_views()
        if self.stats_panel is not None and self.stats_panel.visible:
            self.stats_panel.refresh()
