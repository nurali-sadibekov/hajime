"""Yearly goals overlay: a to-do list per calendar year, opened inside the main window."""

from __future__ import annotations

import tkinter as tk
from datetime import date

import customtkinter as ctk

from .config import (
    ACCENT,
    ACCENT_HOVER,
    BG,
    FAINT,
    INK,
    LINE,
    MAX_GOAL_YEAR,
    MAX_GOALS_PER_YEAR,
    MAX_TASK_TITLE,
    MIN_GOAL_YEAR,
    MUTED,
    ON_ACCENT,
    PANEL,
    TRACK,
)
from .icons import icon
from .models import Goal
from .row_list import RowList

DRAG_THRESHOLD_PX = 6


class GoalsPanel(ctk.CTkFrame):
    """Fills the main window while open, like the activity overlay."""

    def __init__(self, app) -> None:
        super().__init__(app, fg_color=BG, corner_radius=0)
        self.app = app
        self.year = date.today().year
        self.fonts = app.fonts
        self.bind("<Escape>", lambda _e: self.hide())
        self._editing: int | None = None
        self.drag_index: int | None = None
        self._drag_moved = False
        self._empty: ctk.CTkLabel | None = None

        card = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14, border_width=1,
                            border_color=LINE)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 0))
        self._nav(header, "prev", -1)
        self.year_label = ctk.CTkLabel(header, text="", text_color=INK, font=self.fonts["title"],
                                       width=90)
        self.year_label.pack(side="left")
        self._nav(header, "next", 1)
        ctk.CTkButton(
            header, text="", image=icon("close", MUTED, 14), width=28, height=28, corner_radius=8,
            fg_color="transparent", text_color=MUTED, hover_color=TRACK,
            command=self.hide).pack(side="right")
        self.count_label = ctk.CTkLabel(header, text="", text_color=MUTED,
                                        font=self.fonts["body"])
        self.count_label.pack(side="right", padx=(0, 8))

        self.progress = ctk.CTkProgressBar(card, height=6, fg_color=TRACK, progress_color=ACCENT)
        self.progress.pack(fill="x", padx=18, pady=(12, 0))

        add = ctk.CTkFrame(card, fg_color="transparent")
        add.pack(fill="x", padx=18, pady=(12, 6))
        self.entry = ctk.CTkEntry(
            add, placeholder_text="Add a goal for this year…", font=self.fonts["body"],
            height=34, border_width=1, border_color=LINE, fg_color=PANEL, text_color=INK)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda _e: self.add_goal())
        ctk.CTkButton(
            add, text="Add", width=64, height=34, corner_radius=9, font=self.fonts["button"],
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ON_ACCENT,
            command=self.add_goal).pack(
            side="left", padx=(8, 0))

        self.list = ctk.CTkScrollableFrame(
            card, fg_color="transparent", scrollbar_button_color=LINE,
            scrollbar_button_hover_color=FAINT)
        self.list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.rows = RowList(
            self.list, self.fonts, 520, on_toggle=self.toggle, on_delete=self.delete,
            on_press=self._drag_start, on_edit_end=self._end_edit)
        self.refresh()

    # ----- visibility -----------------------------------------------------
    def show(self) -> None:
        self.refresh()
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        self.entry.focus_set()

    def hide(self) -> None:
        self._editing = None
        self.place_forget()

    @property
    def visible(self) -> bool:
        return bool(self.winfo_manager())

    # ----- actions --------------------------------------------------------
    def _nav(self, master: tk.Misc, name: str, step: int) -> None:
        ctk.CTkButton(
            master, text="", image=icon(name, MUTED, 16), width=28, height=28, corner_radius=8,
            fg_color="transparent", text_color=MUTED, hover_color=TRACK,
            command=lambda: self.set_year(self.year + step)).pack(side="left")

    def set_year(self, year: int) -> None:
        self.year = min(max(year, MIN_GOAL_YEAR), MAX_GOAL_YEAR)
        self._editing = None
        self.refresh()

    def _year_goals(self) -> list[Goal]:
        return [g for g in self.app.data.goals if g.year == self.year]

    def add_goal(self) -> None:
        title = self.entry.get().strip()[:MAX_TASK_TITLE]
        if not title or len(self._year_goals()) >= MAX_GOALS_PER_YEAR:
            return
        self.app.data.goals.append(Goal(title, self.year))
        self.entry.delete(0, "end")
        self._changed()

    def toggle(self, index: int) -> None:
        goal = self._year_goals()[index]
        goal.done = not goal.done
        self._changed()

    def delete(self, index: int) -> None:
        self.app.data.goals.remove(self._year_goals()[index])
        self._editing = None
        self._changed()

    def _changed(self) -> None:
        self.app._save()  # persists locally and syncs to Supabase when signed in
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
            self._year_goals()[index].title = title
            self.app._save()
        self.after_idle(self.refresh)

    # ----- drag to reorder (same behaviour as tasks) -----------------------
    def _reorder(self, goals: list[Goal]) -> None:
        data = self.app.data
        data.goals = [g for g in data.goals if g.year != self.year] + goals

    def _drag_start(self, event: tk.Event, index: int) -> None:
        self.drag_index, self._drag_origin_y, self._drag_moved = index, event.y_root, False
        self._drag_bindings = (
            self.app.bind("<B1-Motion>", self._drag_motion, add="+"),
            self.app.bind("<ButtonRelease-1>", self._drag_end, add="+"),
        )

    def _drag_motion(self, event: tk.Event) -> None:
        if self.drag_index is None:
            return
        if not self._drag_moved and abs(event.y_root - self._drag_origin_y) < DRAG_THRESHOLD_PX:
            return
        self._drag_moved = True
        target = next(
            (i for i, row in enumerate(self.rows.frames)
             if row.winfo_rooty() <= event.y_root < row.winfo_rooty() + row.winfo_height()),
            None,
        )
        if target is not None and target != self.drag_index:
            goals = self._year_goals()
            goals.insert(target, goals.pop(self.drag_index))
            self._reorder(goals)
            self.drag_index = target
            self.refresh()

    def _drag_end(self, _event: tk.Event) -> None:
        index, moved = self.drag_index, self._drag_moved
        self.drag_index = None
        motion, release = self._drag_bindings
        self.app.unbind("<B1-Motion>", motion)
        self.app.unbind("<ButtonRelease-1>", release)
        if index is None:
            return
        if moved:
            self._changed()
        else:
            self._begin_edit(index)

    # ----- rendering ------------------------------------------------------
    def refresh(self) -> None:
        goals = self._year_goals()
        done = sum(g.done for g in goals)
        self.year_label.configure(text=str(self.year))
        self.count_label.configure(text=f"{done}/{len(goals)} done" if goals else "No goals yet")
        self.progress.set(done / len(goals) if goals else 0)
        if self._empty is not None:
            self._empty.destroy()
            self._empty = None
        self.rows.sync(goals, self._editing, self.drag_index if self._drag_moved else None)
        if not goals:
            self._empty = ctk.CTkLabel(
                self.list, text=f"Nothing planned for {self.year} yet.", text_color=FAINT,
                font=self.fonts["body"])
            self._empty.pack(pady=24)
