"""Generate packaging/hajime.ico (a white judo belt on a coral tile) with the stdlib only."""

import struct
import sys
import zlib
from pathlib import Path

SIZE = 256
CORAL, WHITE, SHADOW, KNOT = (217, 108, 78), (250, 248, 242), (214, 207, 192), (36, 37, 34)


def inside_round_rect(x, y, size, radius):
    cx = min(max(x, radius), size - 1 - radius)
    cy = min(max(y, radius), size - 1 - radius)
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius**2


def pixel(x, y):
    if not inside_round_rect(x, y, SIZE, 56):
        return (0, 0, 0, 0)
    # belt: a white band across the middle, tilted slightly, with a dark knot in the centre
    band = abs((y - 128) + (x - 128) * 0.12) <= 30
    edge = band and abs((y - 128) + (x - 128) * 0.12) >= 25
    if abs(x - 128) <= 26 and abs(y - 128) <= 34:
        return (*KNOT, 255)
    if edge:
        return (*SHADOW, 255)
    return (*(WHITE if band else CORAL), 255)


def png() -> bytes:
    rows = b"".join(
        b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(SIZE)) for y in range(SIZE))

    def chunk(kind, body):
        crc = zlib.crc32(kind + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("hajime.ico")
    data = png()
    # ICO header, one entry (0 means 256 px), PNG payload
    ico = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(data), 22)
    target.write_bytes(ico + data)
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
