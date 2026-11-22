"""Flicker-free checklist rows shared by the task list and the yearly goals window.

Rows are reused and updated in place; they are only rebuilt when the number of rows changes
or a row switches between viewing and editing. That keeps toggling and drag-reordering smooth.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from types import SimpleNamespace
from typing import Protocol

import customtkinter as ctk

from .config import ACCENT, FAINT, HOVER_ROW, INK, LINE, PANEL
from .icons import icon


class Item(Protocol):
    title: str
    done: bool


class RowList:
    def __init__(self, parent, fonts: dict[str, ctk.CTkFont], wrap: int, *,
                 on_toggle: Callable[[int], None], on_delete: Callable[[int], None],
                 on_press: Callable[[object, int], None],
                 on_edit_end: Callable[[int, ctk.CTkEntry, bool], None]) -> None:
        self.parent, self.fonts, self.wrap = parent, fonts, wrap
        self.on_toggle, self.on_delete = on_toggle, on_delete
        self.on_press, self.on_edit_end = on_press, on_edit_end
        self.rows: list[SimpleNamespace] = []
        self._built_editing: int | None = None

    @property
    def frames(self) -> list[ctk.CTkFrame]:
        return [r.frame for r in self.rows]

    def clear(self) -> None:
        for child in self.parent.winfo_children():
            child.destroy()
        self.rows = []

    def sync(self, items: Sequence[Item], editing: int | None, dragging: int | None) -> None:
        """Make the rows mirror ``items``; ``dragging`` highlights the row being dragged."""
        if len(self.rows) != len(items) or self._built_editing != editing:
            self.clear()
            self._built_editing = editing
            self.rows = [self._build(i, item, editing) for i, item in enumerate(items)]
        for index, (row, item) in enumerate(zip(self.rows, items, strict=True)):
            row.index = index
            self._update(row, item, highlight=index == dragging)

    # ----- internals ------------------------------------------------------
    def _update(self, row: SimpleNamespace, item: Item, highlight: bool) -> None:
        fill = HOVER_ROW if highlight else "transparent"
        if row.fill != fill:
            row.frame.configure(fg_color=fill)
            row.fill = fill
        if bool(row.box.get()) != item.done:
            (row.box.select if item.done else row.box.deselect)()
        if row.label is not None:
            state = (item.title, item.done)
            if row.shown != state:
                row.label.configure(
                    text=item.title, text_color=FAINT if item.done else INK,
                    font=self.fonts["done" if item.done else "body"])
                row.shown = state

    def _build(self, index: int, item: Item, editing: int | None) -> SimpleNamespace:
        frame = ctk.CTkFrame(self.parent, corner_radius=9, fg_color="transparent")
        frame.pack(fill="x", padx=2, pady=1)
        row = SimpleNamespace(frame=frame, index=index, fill="transparent", shown=None,
                              label=None)

        row.box = ctk.CTkCheckBox(
            frame, text="", width=22, checkbox_width=20, checkbox_height=20, corner_radius=6,
            border_width=2, fg_color=ACCENT, hover_color=ACCENT, border_color="#BDBCB5",
            checkmark_color="white",
            command=lambda: frame.after_idle(self.on_toggle, row.index))
        row.box.pack(side="left", padx=(8, 2), pady=7)

        if editing == index:
            edit = ctk.CTkEntry(frame, font=self.fonts["body"], height=28, border_width=1,
                                border_color=LINE, fg_color=PANEL, text_color=INK)
            edit.insert(0, item.title)
            edit.pack(side="left", fill="x", expand=True, padx=(0, 6))
            edit.bind("<Return>", lambda _e: self.on_edit_end(row.index, edit, True))
            edit.bind("<Escape>", lambda _e: self.on_edit_end(row.index, edit, False))
            edit.bind("<FocusOut>", lambda _e: self.on_edit_end(row.index, edit, True))
            edit.focus_set()
            edit.select_range(0, "end")
        else:
            row.label = ctk.CTkLabel(
                frame, text=item.title, anchor="w", justify="left", wraplength=self.wrap,
                text_color=INK, font=self.fonts["body"], cursor="hand2")
            row.label.pack(side="left", fill="x", expand=True, padx=(0, 4))
            row.label.bind("<ButtonPress-1>", lambda e: self.on_press(e, row.index))
            row.shown = (item.title, False)

        remove = ctk.CTkLabel(frame, text="", image=icon("close", FAINT, 12), width=26,
                              height=26, cursor="hand2")
        remove.pack(side="right", padx=(0, 4))
        remove.bind("<Enter>", lambda _e: remove.configure(image=icon("close", ACCENT, 12)))
        remove.bind("<Leave>", lambda _e: remove.configure(image=icon("close", FAINT, 12)))
        remove.bind("<Button-1>", lambda _e: frame.after_idle(self.on_delete, row.index))
        return row
