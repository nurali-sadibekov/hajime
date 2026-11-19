"""Hajime: a persistent to-do list with Judo belts and a Pomodoro timer."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import font as tkfont

from .belt_art import BeltIllustrations
from .config import (
    ACCENT, BG, BELTS, BREAK_SECONDS, DATA_FILE, FONT, INK, LINE, MUTED, PANEL,
    WORK_SECONDS,
)
from .storage import load_data, save_data


class HajimeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hajime — steady progress")
        self.geometry("760x920")
        self.minsize(560, 720)
        self.configure(bg=BG)
        self.tasks, self.study = load_data(DATA_FILE)
        self.timer_mode = "Work"
        self.remaining = WORK_SECONDS
        self.timer_running = False
        self.last_tick = None
        self.timer_job = None
        self.editing_index = None
        self.drag_start_index = None
        self.belt_art = None
        self._configure_fonts()
        self._build()
        self.refresh()
        self._draw_timer()

    def _configure_fonts(self):
        self.option_add("*Font", (FONT, 10))
        self.font_title = tkfont.Font(family=FONT, size=25, weight="bold")
        self.font_heading = tkfont.Font(family=FONT, size=14, weight="bold")
        self.font_body = tkfont.Font(family=FONT, size=11)
        self.font_small = tkfont.Font(family=FONT, size=9)

    def _build(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=48, pady=(27, 26))
        self.progress_card = tk.Frame(
            outer, bg=PANEL, highlightbackground=LINE, highlightthickness=1
        )
        self.progress_card.pack(fill="x", pady=(0, 18))
        content = tk.Frame(self.progress_card, bg=PANEL)
        content.pack(fill="x", padx=24, pady=17)
        belt_row = tk.Frame(content, bg=PANEL)
        belt_row.pack(fill="x")
        belt_text = tk.Frame(belt_row, bg=PANEL)
        belt_text.pack(side="left", fill="x", expand=True)
        self.rank_label = tk.Label(belt_text, text="White belt", bg=PANEL, fg=INK,
                                   font=self.font_title)
        self.rank_label.pack(anchor="w", pady=(4, 0))
        self.belt_canvas = tk.Canvas(belt_row, width=150, height=52, bg=PANEL, highlightthickness=0)
        self.belt_canvas.pack(side="right", padx=(12, 0), pady=(6, 0))
        self.belt_art = BeltIllustrations(self.belt_canvas)
        self.progress_canvas = tk.Canvas(content, height=7, bg="#EEEDE8", highlightthickness=0)
        self.progress_canvas.pack(fill="x", pady=(16, 8))
        meta = tk.Frame(content, bg=PANEL)
        meta.pack(fill="x")
        self.progress_label = tk.Label(meta, text="0%", bg=PANEL, fg=INK,
                                       font=(FONT, 10, "bold"))
        self.progress_label.pack(side="left")

        self.timer_card = tk.Frame(outer, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        self.timer_card.pack(fill="x", pady=(0, 16))
        timer_content = tk.Frame(self.timer_card, bg=PANEL)
        timer_content.pack(fill="x", padx=20, pady=13)
        self.timer_display = tk.Label(timer_content, text="25:00", bg=PANEL, fg=INK,
                                      font=(FONT, 23, "bold"))
        self.timer_display.pack(side="left", padx=(0, 20))
        self.timer_button = tk.Button(timer_content, text="Start", command=self.toggle_timer,
                                      bg=INK, fg="white", activebackground="#41433E",
                                      activeforeground="white", relief="flat", bd=0,
                                      cursor="hand2", padx=15, pady=7)
        self.timer_button.pack(side="left")
        self.reset_button = tk.Button(timer_content, text="Reset", command=self.reset_timer,
                                      bg=PANEL, fg=MUTED, activebackground=PANEL,
                                      activeforeground=INK, relief="flat", bd=0, cursor="hand2")
        self.reset_button.pack(side="left", padx=(7, 0))
        self.studied_label = tk.Label(timer_content, text="Today · 0m studied", bg=PANEL,
                                      fg=MUTED, font=self.font_small)
        self.studied_label.pack(side="right", anchor="center")

        section = tk.Frame(outer, bg=BG)
        section.pack(fill="x", pady=(0, 9))
        tk.Label(section, text="Your list", bg=BG, fg=INK, font=self.font_heading).pack(side="left")
        add_card = tk.Frame(outer, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        add_card.pack(fill="x", pady=(0, 11))
        self.entry = tk.Entry(add_card, bg=PANEL, fg=INK, insertbackground=INK,
                              relief="flat", bd=0, font=self.font_body)
        self.entry.pack(side="left", fill="x", expand=True, padx=(15, 8), ipady=11)
        self.entry.insert(0, "Add task")
        self.entry.config(fg=MUTED)
        self.entry.bind("<FocusIn>", self._entry_focus)
        self.entry.bind("<FocusOut>", self._entry_blur)
        self.entry.bind("<Return>", lambda _event: self.add_task())
        tk.Button(add_card, text="+", command=self.add_task, bg=INK, fg="white",
                  activebackground="#41433E", activeforeground="white", relief="flat", bd=0,
                  cursor="hand2", font=(FONT, 16), width=3).pack(side="right", padx=7, pady=6)

        list_shell = tk.Frame(outer, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        list_shell.pack(fill="both", expand=True)
        self.list_canvas = tk.Canvas(list_shell, bg=PANEL, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(list_shell, orient="vertical", command=self.list_canvas.yview,
                                 relief="flat", bd=0, width=8)
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.list_canvas.pack(side="left", fill="both", expand=True)
        self.task_frame = tk.Frame(self.list_canvas, bg=PANEL)
        self.task_window = self.list_canvas.create_window(
            (0, 0), window=self.task_frame, anchor="nw"
        )
        self.task_frame.bind("<Configure>", self._on_list_configure)
        self.list_canvas.bind("<Configure>", self._on_canvas_configure)
        self.list_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _entry_focus(self, _event):
        if self.entry.get() == "Add task":
            self.entry.delete(0, "end")
            self.entry.config(fg=INK)

    def _entry_blur(self, _event):
        if not self.entry.get().strip():
            self.entry.delete(0, "end")
            self.entry.insert(0, "Add task")
            self.entry.config(fg=MUTED)

    def _on_list_configure(self, _event):
        self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.list_canvas.itemconfigure(self.task_window, width=event.width)

    def _on_mousewheel(self, event):
        if self.winfo_containing(event.x_root, event.y_root) in (self.list_canvas, self.task_frame):
            self.list_canvas.yview_scroll(int(-event.delta / 120), "units")

    def add_task(self):
        title = self.entry.get().strip()
        if not title or title == "Add task":
            return
        self.tasks.append({"title": title, "done": False})
        self.entry.delete(0, "end")
        self.entry.config(fg=INK)
        self._save()
        self.refresh()
        self.entry.focus_set()

    def toggle_task(self, index):
        was_done = self.tasks[index]["done"]
        self.tasks[index]["done"] = not was_done
        self._save()
        self.refresh()

    def edit_task(self, index):
        if self.editing_index == index:
            return
        self.editing_index = index
        self.refresh()

    def commit_edit(self, index, entry):
        title = entry.get().strip()
        if title:
            self.tasks[index]["title"] = title
            self._save()
        self.editing_index = None
        self.refresh()

    def begin_task_drag(self, event, index):
        self.drag_start_index = index
        self.drag_origin_y = event.y_root
        self.drag_moved = False
        self.bind_all("<B1-Motion>", self.drag_task)
        self.bind_all("<ButtonRelease-1>", self.end_task_drag)
        return "break"

    def drag_task(self, event):
        if self.drag_start_index is None:
            return "break"
        if abs(event.y_root - self.drag_origin_y) < 8:
            return "break"
        self.drag_moved = True
        pointer_y = self.list_canvas.canvasy(event.y_root - self.list_canvas.winfo_rooty())
        target_index = min(
            max(0, int(pointer_y / max(1, self.task_frame.winfo_height()) * len(self.tasks))),
            len(self.tasks) - 1,
        )
        if target_index != self.drag_start_index:
            task = self.tasks.pop(self.drag_start_index)
            self.tasks.insert(target_index, task)
            self.drag_start_index = target_index
            self.refresh()
        return "break"

    def end_task_drag(self, event):
        if self.drag_start_index is not None:
            index = self.drag_start_index
            self.drag_start_index = None
            self.unbind_all("<B1-Motion>")
            self.unbind_all("<ButtonRelease-1>")
            if not self.drag_moved:
                self.edit_task(index)
            self._save()
        return "break"

    def delete_task(self, index):
        del self.tasks[index]
        self._save()
        self.refresh()

    def _save(self):
        try:
            save_data(DATA_FILE, self.tasks, self.study)
        except OSError:
            pass

    def toggle_timer(self):
        self.timer_running = not self.timer_running
        self.timer_button.config(text="Pause" if self.timer_running else "Start")
        if self.timer_running:
            self.last_tick = time.monotonic()
            self._timer_tick()
        elif self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None
            self.last_tick = None

    def reset_timer(self):
        self.timer_running = False
        if self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        self.last_tick = None
        self.remaining = WORK_SECONDS if self.timer_mode == "Work" else BREAK_SECONDS
        self.timer_button.config(text="Start")
        self._draw_timer()

    def _timer_tick(self):
        if not self.timer_running:
            return
        now = time.monotonic()
        elapsed = max(1, int(now - self.last_tick)) if self.last_tick is not None else 1
        self.last_tick = now
        if self.remaining <= 0:
            self.timer_running = False
            self.timer_button.config(text="Start")
            self.timer_job = None
            self.last_tick = None
            self.timer_mode = "Break" if self.timer_mode == "Work" else "Work"
            self.remaining = BREAK_SECONDS if self.timer_mode == "Break" else WORK_SECONDS
            self._draw_timer()
            self.bell()
            return
        elapsed = min(elapsed, self.remaining)
        if self.timer_mode == "Work":
            self.study["seconds"] += elapsed
            self._save()
        self.remaining -= elapsed
        self._draw_timer()
        self.timer_job = self.after(1000, self._timer_tick)

    def _draw_timer(self):
        mins, secs = divmod(max(0, self.remaining), 60)
        self.timer_display.config(text=f"{mins:02d}:{secs:02d}")
        seconds = self.study.get("seconds", 0)
        hours, rem = divmod(seconds, 3600)
        studied = f"{hours}h {rem // 60}m" if hours else f"{seconds // 60}m"
        self.studied_label.config(text=studied)

    @staticmethod
    def _belt_state(fraction):
        if fraction >= 1:
            return len(BELTS) - 1
        rank_position = max(0.0, fraction * (len(BELTS) - 1))
        return min(int(rank_position), len(BELTS) - 2)

    def refresh(self):
        total = len(self.tasks)
        complete = sum(1 for task in self.tasks if task["done"])
        fraction = complete / total if total else 0.0
        rank = self._belt_state(fraction)
        name, _color, _edge = BELTS[rank]
        self.rank_label.config(text=f"{name} belt")
        self.belt_art.draw(rank)
        self.progress_label.config(text=f"{round(fraction * 100)}%")
        self.progress_canvas.delete("all")
        self.progress_canvas.update_idletasks()
        width = max(self.progress_canvas.winfo_width(), 20)
        self.progress_canvas.create_rectangle(0, 0, width * fraction, 7, fill=ACCENT, outline="")

        for child in self.task_frame.winfo_children():
            child.destroy()
        if not self.tasks:
            return
        for index, task in enumerate(self.tasks):
            row = tk.Frame(self.task_frame, bg=PANEL)
            row.pack(fill="x", padx=18)
            if index:
                tk.Frame(row, bg=LINE, height=1).pack(fill="x")
            inner = tk.Frame(row, bg=PANEL)
            inner.pack(fill="x", pady=9)
            done = task["done"]
            check = tk.Canvas(inner, width=20, height=20, bg=PANEL, highlightthickness=0,
                              bd=0, cursor="hand2")
            check.pack(side="left", padx=(0, 10))
            check.create_rectangle(1, 1, 18, 18, fill=ACCENT if done else PANEL,
                                   outline=ACCENT if done else "#BDBCB5", width=1)
            if done:
                check.create_text(9.5, 9.5, text="✓", fill="white", font=(FONT, 9, "bold"))
            check.bind("<Button-1>", lambda _event, i=index: self.toggle_task(i))
            if self.editing_index == index:
                edit = tk.Entry(inner, font=self.font_body, relief="flat", bd=0)
                edit.insert(0, task["title"])
                edit.pack(side="left", fill="x", expand=True)
                edit.bind("<Return>", lambda _e, i=index, w=edit: self.commit_edit(i, w))
                edit.bind("<FocusOut>", lambda _e, i=index, w=edit: self.commit_edit(i, w))
                edit.focus_set()
            else:
                label = tk.Label(inner, text=task["title"], bg=PANEL,
                                 fg="#A3A29B" if done else INK, font=self.font_body,
                                 anchor="w", justify="left", wraplength=390, cursor="hand2")
                label.pack(side="left", fill="x", expand=True)
                label.bind("<ButtonPress-1>", lambda e, i=index: self.begin_task_drag(e, i))
                if done:
                    label.config(font=(FONT, 11, "overstrike"))
            tools = tk.Frame(inner, bg=PANEL)
            tools.pack(side="right")
            tk.Button(
                tools,
                text="×",
                command=lambda i=index: self.delete_task(i),
                bg=PANEL,
                fg="#AAA9A2",
                activebackground=PANEL,
                activeforeground=ACCENT,
                relief="flat",
                bd=0,
                cursor="hand2",
                font=(FONT, 15),
                width=2,
            ).pack(side="left")


if __name__ == "__main__":
    HajimeApp().mainloop()
