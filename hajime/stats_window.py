"""Study-activity window: a GitHub-style contribution heatmap per year."""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date

import customtkinter as ctk

from . import stats
from .config import ACCENT, BG, FAINT, HEAT_COLORS, INK, LINE, MUTED, PANEL, TRACK

CELL, GAP = 11, 3
STEP = CELL + GAP
LEFT, TOP = 32, 20
DAY_LABELS = {0: "Mon", 2: "Wed", 4: "Fri"}
MONTH_BAR_H = 60


class StatsWindow(ctk.CTkToplevel):
    def __init__(self, app) -> None:
        super().__init__(app, fg_color=BG)
        self.app = app
        self.year = date.today().year
        self.title("Hajime · Activity")
        self.resizable(False, False)
        self.fonts = app.fonts

        width = LEFT + 53 * STEP + 24
        self.geometry(f"{width + 32}x470")

        card = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14, border_width=1,
                            border_color=LINE)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 0))
        self.prev_button = self._nav(header, "‹", -1)
        self.year_label = ctk.CTkLabel(header, text="", text_color=INK, font=self.fonts["title"],
                                       width=90)
        self.year_label.pack(side="left")
        self.next_button = self._nav(header, "›", 1)
        self.total_label = ctk.CTkLabel(header, text="", text_color=MUTED, font=self.fonts["body"])
        self.total_label.pack(side="right")

        self.heat = tk.Canvas(card, width=LEFT + 53 * STEP, height=TOP + 7 * STEP,
                              bg=PANEL, highlightthickness=0)
        self.heat.pack(padx=18, pady=(12, 0), anchor="w")

        legend = ctk.CTkFrame(card, fg_color="transparent")
        legend.pack(fill="x", padx=18, pady=(4, 0))
        self.hover_label = ctk.CTkLabel(legend, text=" ", text_color=MUTED,
                                        font=self.fonts["small"])
        self.hover_label.pack(side="left")
        ctk.CTkLabel(legend, text="More", text_color=FAINT, font=self.fonts["small"]).pack(
            side="right")
        for color in reversed(HEAT_COLORS):
            tk.Frame(legend, width=CELL, height=CELL, bg=color).pack(side="right", padx=1)
        ctk.CTkLabel(legend, text="Less", text_color=FAINT, font=self.fonts["small"]).pack(
            side="right", padx=(0, 4))

        self.summary = ctk.CTkLabel(card, text="", text_color=INK, font=self.fonts["body"],
                                    anchor="w", justify="left")
        self.summary.pack(fill="x", padx=18, pady=(8, 0))

        ctk.CTkLabel(card, text="By month", text_color=MUTED, font=self.fonts["small"],
                     anchor="w").pack(fill="x", padx=18, pady=(8, 0))
        self.months = tk.Canvas(card, width=LEFT + 53 * STEP, height=MONTH_BAR_H + 34,
                                bg=PANEL, highlightthickness=0)
        self.months.pack(padx=18, pady=(0, 10), anchor="w")
        self.refresh()

    def _nav(self, master: tk.Misc, text: str, step: int) -> ctk.CTkButton:
        button = ctk.CTkButton(
            master, text=text, width=28, height=28, corner_radius=8, font=self.fonts["icon"],
            fg_color="transparent", text_color=MUTED, hover_color=TRACK,
            command=lambda: self.set_year(self.year + step))
        button.pack(side="left")
        return button

    def set_year(self, year: int) -> None:
        first, last = stats.years_available(self.app.data.history)
        self.year = min(max(year, first), last)
        self.refresh()

    def refresh(self) -> None:
        history = self.app.data.history
        first, last = stats.years_available(history)
        self.year = min(max(self.year, first), last)
        self.year_label.configure(text=str(self.year))
        self.prev_button.configure(state="normal" if self.year > first else "disabled")
        self.next_button.configure(state="normal" if self.year < last else "disabled")
        total = stats.year_total(history, self.year)
        self.total_label.configure(text=f"{stats.fmt_duration(total)} studied in {self.year}")
        current, longest = stats.streaks(history)
        self.summary.configure(
            text=f"Active days: {stats.active_days(history, self.year)}     "
                 f"Current streak: {current}d     Longest streak: {longest}d     "
                 f"Today: {stats.fmt_duration(self.app.data.focus_seconds)}")
        self._draw_heatmap(history)
        self._draw_months(history)

    def _draw_heatmap(self, history: dict[str, int]) -> None:
        canvas = self.heat
        canvas.delete("all")
        weeks = stats.year_weeks(self.year)
        for row, label in DAY_LABELS.items():
            canvas.create_text(0, TOP + row * STEP + CELL / 2, text=label, anchor="w",
                               fill=FAINT, font=self.fonts["small"])
        for col, week in enumerate(weeks):
            x = LEFT + col * STEP
            for row, day in enumerate(week):
                if day is None:
                    continue
                seconds = stats.seconds_on(history, day)
                y = TOP + row * STEP
                rect = canvas.create_rectangle(
                    x, y, x + CELL, y + CELL, width=0,
                    fill=HEAT_COLORS[stats.level(seconds)])
                text = (f"{stats.fmt_duration(seconds)} on {day:%a, %b} {day.day}, {day.year}"
                        if seconds else f"No study on {day:%a, %b} {day.day}, {day.year}")
                canvas.tag_bind(rect, "<Enter>", lambda _e, t=text: self.hover_label.configure(
                    text=t))
                canvas.tag_bind(rect, "<Leave>", lambda _e: self.hover_label.configure(text=" "))
            month_start = next((d for d in week if d is not None and d.day == 1), None)
            if month_start:  # label the column holding the 1st of each month
                canvas.create_text(x, 2, text=calendar.month_abbr[month_start.month],
                                   anchor="nw", fill=MUTED, font=self.fonts["small"])

    def _draw_months(self, history: dict[str, int]) -> None:
        canvas = self.months
        canvas.delete("all")
        totals = stats.month_totals(history, self.year)
        peak = max(totals) or 1
        slot = (53 * STEP) / 12
        for index, seconds in enumerate(totals):
            x = LEFT + index * slot
            height = 0 if not seconds else max(3, int(seconds / peak * MONTH_BAR_H))
            bottom = 16 + MONTH_BAR_H
            canvas.create_rectangle(x + 8, bottom - height, x + slot - 8, bottom, width=0,
                                    fill=ACCENT if seconds else TRACK)
            if seconds:
                canvas.create_text(x + slot / 2, bottom - height - 2, text=stats.fmt_duration(
                    seconds), anchor="s", fill=MUTED, font=self.fonts["small"])
            canvas.create_text(x + slot / 2, bottom + 4, text=calendar.month_abbr[index + 1],
                               anchor="n", fill=MUTED, font=self.fonts["small"])
