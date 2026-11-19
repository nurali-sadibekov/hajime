"""Static configuration: belts, timer durations and the visual theme."""

from pathlib import Path

BELT_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "belts"

# (display name, fallback fill, fallback edge)
BELTS = (
    ("White", "#F4F1E9", "#D8D2C5"),
    ("Yellow", "#F4CD55", "#C39B31"),
    ("Orange", "#ED9850", "#C56E2D"),
    ("Green", "#6B9A70", "#49734E"),
    ("Blue", "#638BC1", "#426B9E"),
    ("Brown", "#956448", "#70452F"),
    ("Black", "#292C31", "#17191C"),
)

WORK_SECONDS = 25 * 60
BREAK_SECONDS = 5 * 60
SAVE_INTERVAL_SECONDS = 15

# Theme
BG = "#F5F4F0"
PANEL = "#FFFFFF"
INK = "#242522"
INK_HOVER = "#41433E"
MUTED = "#898982"
FAINT = "#A3A29B"
LINE = "#E9E8E2"
TRACK = "#EEEDE8"
ACCENT = "#D96C4E"
ACCENT_BREAK = "#6B9A70"
HOVER_ROW = "#FAF9F6"
ACTIVE_BG = "#FAE9E3"
ACCENT_HOVER = "#C45B3E"
MAX_BOARD_NAME = 24
MAX_TASK_TITLE = 200
FONT_CANDIDATES = ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Ubuntu", "DejaVu Sans")
