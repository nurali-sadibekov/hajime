"""Crisp vector-style icons drawn with Pillow.

Font glyphs (x, +, <, ...) sit off-centre inside buttons because of font ascent metrics.
Images are centred exactly, look identical on every platform and stay sharp (supersampled).
"""

from __future__ import annotations

from functools import cache

import customtkinter as ctk
from PIL import Image, ImageDraw

SCALE = 8  # supersampling factor; CTkImage scales down smoothly


def icon(name: str, color: str, size: int = 16) -> ctk.CTkImage:
    """Return a ``size``x``size`` icon in ``color``.

    Names: ``plus``, ``close``, ``prev``, ``next``, ``pip``, ``activity``, ``goals``.
    """
    image = _render(name, color, size)
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))


@cache
def _render(name: str, color: str, size: int) -> Image.Image:
    # Only the Pillow bitmap is cached: CTkImage objects are bound to a Tk root.
    px = size * SCALE
    image = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    stroke = max(1, round(size * 0.11 * SCALE))
    c = px / 2

    def line(points: list[tuple[float, float]]) -> None:
        draw.line(points, fill=color, width=stroke, joint="curve")
        r = stroke / 2
        for x, y in (points[0], points[-1]):  # round caps
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color)

    a, b = px * 0.28, px * 0.72  # glyph extent
    if name == "plus":
        line([(a, c), (b, c)])
        line([(c, a), (c, b)])
    elif name == "close":
        line([(a, a), (b, b)])
        line([(a, b), (b, a)])
    elif name in ("prev", "next"):
        near, far = px * 0.38, px * 0.62
        tip, base = (near, far) if name == "prev" else (far, near)
        line([(base, px * 0.24), (tip, c), (base, px * 0.76)])
    elif name == "pip":  # picture-in-picture: window outline + floating tile
        m = px * 0.14
        draw.rounded_rectangle((m, m + px * 0.04, px - m, px - m - px * 0.04),
                               radius=px * 0.12, outline=color, width=stroke)
        draw.rounded_rectangle((px * 0.5, px * 0.5, px - m - px * 0.07, px - m - px * 0.11),
                               radius=px * 0.05, fill=color)
    elif name == "activity":  # 3x3 heat grid
        gap = px * 0.07
        cell = (px * 0.76 - 2 * gap) / 3
        for row in range(3):
            for col in range(3):
                x = px * 0.12 + col * (cell + gap)
                y = px * 0.12 + row * (cell + gap)
                shade = color if (row + col) % 2 == 0 else color + "88"
                draw.rounded_rectangle((x, y, x + cell, y + cell), radius=px * 0.04, fill=shade)
    elif name == "goals":  # target
        m = px * 0.13
        draw.ellipse((m, m, px - m, px - m), outline=color, width=stroke)
        m2 = px * 0.32
        draw.ellipse((m2, m2, px - m2, px - m2), outline=color, width=stroke)
        r = px * 0.07
        draw.ellipse((c - r, c - r, c + r, c + r), fill=color)
    else:
        raise ValueError(f"unknown icon {name!r}")
    return image
