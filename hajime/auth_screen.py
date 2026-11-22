"""Minimal full-window sign-in screen shown before the app."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from .config import ACCENT, BG, INK, LINE, MUTED, PANEL, TRACK


class AuthScreen(ctk.CTkFrame):
    def __init__(self, master, fonts: dict[str, ctk.CTkFont], on_google: Callable[[], None],
                 on_cancel: Callable[[], None], on_offline: Callable[[], None]) -> None:
        super().__init__(master, fg_color=BG, corner_radius=0)
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.place(relx=0.5, rely=0.46, anchor="center")

        ctk.CTkLabel(box, text="Hajime", text_color=INK,
                     font=fonts["title"]).pack()
        ctk.CTkLabel(box, text="Your tasks and belts, on every device.", text_color=MUTED,
                     font=fonts["body"]).pack(pady=(4, 28))

        self.google = ctk.CTkButton(
            box, text="G   Continue with Google", width=280, height=44, corner_radius=12,
            font=fonts["button"], fg_color=PANEL, hover_color=TRACK, text_color=INK,
            border_width=1, border_color=LINE, command=on_google)
        self.google.pack()
        self.cancel = ctk.CTkButton(
            box, text="Cancel", width=280, height=32, corner_radius=10, font=fonts["small"],
            fg_color="transparent", hover_color=TRACK, text_color=MUTED, command=on_cancel)
        self.status = ctk.CTkLabel(box, text="", text_color=MUTED, font=fonts["small"],
                                   wraplength=280, justify="center")
        self.status.pack(pady=(12, 0))
        self.hint = ctk.CTkLabel(
            box, text="New here? An account is created automatically.",
            text_color=MUTED, font=fonts["small"])
        self.hint.pack(pady=(4, 0))
        self.offline = ctk.CTkButton(
            box, text="Use without an account", width=280, height=28, corner_radius=10,
            font=fonts["small"], fg_color="transparent", hover_color=TRACK, text_color=MUTED,
            command=on_offline)

    def show(self) -> None:
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

    def hide(self) -> None:
        self.place_forget()

    def idle(self, message: str = "", error: bool = False, configured: bool = True) -> None:
        """Ready for input; ``configured=False`` explains how to set Supabase up."""
        self.cancel.pack_forget()
        self.google.configure(state="normal" if configured else "disabled")
        self.status.configure(text=message, text_color=ACCENT if error else MUTED)
        if configured:
            self.hint.pack(pady=(4, 0))
            self.offline.pack_forget()
        else:
            self.hint.pack_forget()
            self.offline.pack(pady=(10, 0))

    def busy(self, message: str, cancellable: bool = False) -> None:
        self.google.configure(state="disabled")
        self.offline.pack_forget()
        self.status.configure(text=message, text_color=MUTED)
        if cancellable:
            self.cancel.pack(pady=(6, 0))
        else:
            self.cancel.pack_forget()

