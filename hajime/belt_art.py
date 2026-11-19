"""Load Wikimedia Commons belt illustrations, with a Tk-only fallback."""

from __future__ import annotations

import base64
from pathlib import Path
import re
import tkinter as tk
import xml.etree.ElementTree as ET

from .config import BELT_ASSET_DIR, BELTS


class BeltIllustrations:
    """Render SVG belt art when CairoSVG is installed; otherwise draw in Tk."""

    def __init__(self, canvas: tk.Canvas, asset_dir: Path = BELT_ASSET_DIR):
        self.canvas = canvas
        self.asset_dir = asset_dir
        self._photo = None  # Keep a live reference; Tk images are otherwise collected.

    def draw(self, rank: int) -> None:
        self.canvas.delete("all")
        asset = self.asset_dir / f"{BELTS[rank][0].lower()}.svg"
        if self._draw_svg(asset):
            return
        self._draw_native(BELTS[rank][1], BELTS[rank][2])

    def _draw_svg(self, asset: Path) -> bool:
        if not asset.is_file():
            return False
        try:
            import cairosvg

            png = cairosvg.svg2png(url=str(asset), output_width=150, output_height=58)
            self._photo = tk.PhotoImage(data=base64.b64encode(png).decode("ascii"), format="png")
            self.canvas.create_image(75, 29, image=self._photo)
            return True
        except Exception:
            # SVG engines and Tk builds vary; the native renderer is the
            # dependency-free fallback for any conversion or image error.
            return self._draw_svg_with_tk(asset)

    def _draw_svg_with_tk(self, asset: Path) -> bool:
        """Draw the belt SVG's M/C/L/Z paths with Tk, without extra packages."""
        try:
            root = ET.fromstring(asset.read_text(encoding="utf-8"))
            view_box = [float(value) for value in root.attrib["viewBox"].split()]
            min_x, min_y, source_width, source_height = view_box
            width, height = self.canvas.winfo_reqwidth(), self.canvas.winfo_reqheight()
            scale = min((width - 8) / source_width, (height - 8) / source_height)
            offset_x = (width - source_width * scale) / 2 - min_x * scale
            offset_y = (height - source_height * scale) / 2 - min_y * scale

            for element in root.iter():
                if not element.tag.endswith("path"):
                    continue
                points = self._path_points(element.attrib.get("d", ""))
                if len(points) < 3:
                    continue
                coordinates = [coordinate for x, y in points
                               for coordinate in (offset_x + x * scale, offset_y + y * scale)]
                self.canvas.create_polygon(
                    *coordinates,
                    fill=element.attrib.get("fill", "black"),
                    outline=element.attrib.get("stroke", ""),
                    width=max(1, float(element.attrib.get("stroke-width", 1)) * scale),
                    joinstyle="round",
                )
            return True
        except (ET.ParseError, OSError, KeyError, ValueError):
            return False

    @staticmethod
    def _path_points(path: str) -> list[tuple[float, float]]:
        tokens = re.findall(r"[MmCcSsLlZz]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?", path)
        points: list[tuple[float, float]] = []
        index = 0
        command = None
        x = y = 0.0
        start = (0.0, 0.0)
        previous_control = None

        def number_pair(position: int) -> tuple[float, float, int]:
            return float(tokens[position]), float(tokens[position + 1]), position + 2

        while index < len(tokens):
            if tokens[index].isalpha():
                command = tokens[index]
                index += 1
                if command in "Zz":
                    x, y = start
                    points.append(start)
                    command = None
                    continue
            if command is None:
                continue
            if command in "MmLl":
                nx, ny, index = number_pair(index)
                if command.islower():
                    nx, ny = x + nx, y + ny
                x, y = nx, ny
                points.append((x, y))
                previous_control = None
                if command in "Mm":
                    start = (x, y)
                    command = "l" if command == "m" else "L"
            elif command in "Cc":
                values = [float(value) for value in tokens[index:index + 6]]
                if len(values) != 6:
                    break
                index += 6
                x1, y1, x2, y2, x3, y3 = values
                if command == "c":
                    x1, y1, x2, y2, x3, y3 = x + x1, y + y1, x + x2, y + y2, x + x3, y + y3
                x0, y0 = x, y
                for step in range(1, 9):
                    t = step / 8
                    u = 1 - t
                    points.append((u**3*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3,
                                   u**3*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3))
                x, y = x3, y3
                previous_control = (x2, y2)
            elif command in "Ss":
                values = [float(value) for value in tokens[index:index + 4]]
                if len(values) != 4:
                    break
                index += 4
                x1, y1 = ((2 * x - previous_control[0], 2 * y - previous_control[1])
                          if previous_control else (x, y))
                x2, y2, x3, y3 = values[0], values[1], values[2], values[3]
                if command == "s":
                    x2, y2, x3, y3 = x + x2, y + y2, x + x3, y + y3
                x0, y0 = x, y
                for step in range(1, 9):
                    t = step / 8
                    u = 1 - t
                    points.append((u**3*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3,
                                   u**3*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3))
                x, y = x3, y3
                previous_control = (x2, y2)
            else:
                return []
        return points

    def _draw_native(self, color: str, edge: str) -> None:
        """Simple vector fallback keeps the app dependency-free."""
        c = self.canvas
        c.create_polygon(12, 17, 129, 17, 143, 26, 29, 26, fill=edge, outline=edge)
        c.create_rectangle(12, 12, 128, 21, fill=color, outline=edge, width=1)
        c.create_polygon(128, 12, 145, 19, 139, 42, 126, 36, fill=color, outline=edge, width=1)
        c.create_polygon(128, 18, 145, 25, 142, 30, 126, 23, fill=edge, outline=edge)
        c.create_rectangle(72, 11, 83, 22, fill=edge, outline=edge)
        c.create_line(75, 12, 75, 21, fill="#FFFFFF", stipple="gray50")
