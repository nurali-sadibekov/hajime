"""The app's typeface: Inter in two weights (Regular and SemiBold) and three sizes.

The font files ship with the app and are registered for this process only, so nothing is
installed system-wide. If registration fails the UI falls back to a system font.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

import customtkinter as ctk

from .config import FONT_CANDIDATES

LOG = logging.getLogger("hajime")

FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
FILES = ("Inter-Regular.ttf", "Inter-SemiBold.ttf")
REGULAR, SEMIBOLD = "Inter", "Inter SemiBold"

SMALL, BODY, LARGE = 12, 14, 24  # the only three sizes used anywhere in the UI


def _register(path: Path) -> None:
    if sys.platform == "win32":
        FR_PRIVATE = 0x10  # visible to this process only
        if not ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0):
            raise OSError(f"could not register {path.name}")
    elif sys.platform == "darwin":
        core = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreText.framework/CoreText")
        foundation = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        foundation.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
        foundation.CFURLCreateFromFileSystemRepresentation.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_bool]
        url = foundation.CFURLCreateFromFileSystemRepresentation(
            None, str(path).encode(), len(str(path).encode()), False)
        core.CTFontManagerRegisterFontsForURL.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        if not core.CTFontManagerRegisterFontsForURL(url, 1, None):  # kCTFontManagerScopeProcess
            raise OSError(f"could not register {path.name}")
    else:
        fontconfig = ctypes.cdll.LoadLibrary("libfontconfig.so.1")
        fontconfig.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        if not fontconfig.FcConfigAppFontAddFile(None, str(path).encode()):
            raise OSError(f"could not register {path.name}")


def load_inter(root: tk.Misc) -> bool:
    """Register the bundled Inter files; True when both weights are usable by Tk."""
    try:
        for name in FILES:
            _register(FONT_DIR / name)
    except (OSError, AttributeError):
        LOG.warning("could not load the bundled Inter font", exc_info=True)
        return False
    families = set(tkfont.families(root))
    return REGULAR in families and SEMIBOLD in families


def build_fonts(root: tk.Misc) -> dict[str, ctk.CTkFont]:
    """Create the named fonts used across the UI."""
    if load_inter(root):
        regular, semibold, weight = REGULAR, SEMIBOLD, "normal"
    else:
        available = set(tkfont.families(root))
        regular = semibold = next(
            (f for f in FONT_CANDIDATES if f in available),
            tkfont.nametofont("TkDefaultFont").actual("family"))
        weight = "bold"

    def make(family: str, size: int, bold: bool = False, **extra) -> ctk.CTkFont:
        return ctk.CTkFont(family, size, weight if bold else "normal", **extra)

    return {
        "small": make(regular, SMALL),
        "body": make(regular, BODY),
        "done": make(regular, BODY, overstrike=True),
        "button": make(semibold, BODY, bold=True),
        "title": make(semibold, LARGE, bold=True),
    }
