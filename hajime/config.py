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
ACCENT = "#8C2B3A"  # maroon
ACCENT_BREAK = "#6B9A70"
HOVER_ROW = "#FAF9F6"
ACTIVE_BG = "#F6E8EA"
ACCENT_HOVER = "#721F2E"
HEAT_COLORS = (TRACK, "#EFD6DA", "#DBA3AC", "#B96672", ACCENT)  # level 0..4
MAX_BOARD_NAME = 24
MAX_TASK_TITLE = 200
MAX_BOARDS = 30
MAX_TASKS_PER_BOARD = 300
MAX_HISTORY_DAYS = 3660
MAX_GOALS_PER_YEAR = 100
MIN_GOAL_YEAR, MAX_GOAL_YEAR = 2000, 2100
SECONDS_PER_DAY = 86400
FONT_CANDIDATES = ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Ubuntu", "DejaVu Sans")
