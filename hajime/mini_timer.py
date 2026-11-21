"""Small borderless always-on-top timer that floats above every other window."""

from __future__ import annotations

import customtkinter as ctk

from .config import ACCENT_BREAK, INK, INK_HOVER, LINE, MUTED, PANEL, TRACK


class MiniTimer(ctk.CTkToplevel):
    def __init__(self, app) -> None:
        super().__init__(app, fg_color=PANEL)
        self.app = app
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self._drag = (0, 0)

        frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, border_width=1,
                             border_color=LINE)
        frame.pack(fill="both", expand=True)
        self.clock = ctk.CTkLabel(frame, text="", text_color=INK, font=app.fonts["clock"])
        self.clock.pack(side="left", padx=(14, 8), pady=8)
        self.button = ctk.CTkButton(
            frame, text="Start", width=64, height=30, corner_radius=8,
            font=app.fonts["button"], fg_color=INK, hover_color=INK_HOVER,
            command=app.toggle_timer)
        self.button.pack(side="left", pady=8)
        close = ctk.CTkButton(
            frame, text="×", width=26, height=26, corner_radius=8, font=app.fonts["icon"],
            fg_color="transparent", text_color=MUTED, hover_color=TRACK, command=self.hide)
        close.pack(side="left", padx=(4, 8), pady=8)

        for widget in (frame, self.clock):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_motion)
        self.geometry(f"+{self.winfo_screenwidth() - 300}+40")

    def _drag_start(self, event) -> None:
        self._drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag_motion(self, event) -> None:
        self.geometry(f"+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}")

    @property
    def visible(self) -> bool:
        return self.state() != "withdrawn"

    def show(self) -> None:
        self.deiconify()
        self.attributes("-topmost", True)
        self.lift()

    def hide(self) -> None:
        self.withdraw()
        self.app.on_mini_hidden()

    def update_state(self, clock: str, running: bool, on_break: bool) -> None:
        self.clock.configure(text=clock, text_color=ACCENT_BREAK if on_break else INK)
        self.button.configure(text="Pause" if running else "Start")
