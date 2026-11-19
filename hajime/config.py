"""Application settings and visual theme."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "hajime_tasks.json"
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

BG = "#F5F4F0"
PANEL = "#FFFFFF"
INK = "#242522"
MUTED = "#898982"
LINE = "#E9E8E2"
ACCENT = "#D96C4E"
FONT = "Segoe UI"

WORK_SECONDS = 25 * 60
BREAK_SECONDS = 5 * 60
