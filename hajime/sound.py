"""Timer-finished ringtone, synthesised in memory (no audio asset needed)."""

from __future__ import annotations

import io
import math
import struct
import sys
import wave

RATE = 22050
# (frequency Hz, seconds): a rising three-note chime, repeated twice.
_MELODY = [(784, 0.16), (988, 0.16), (1319, 0.40)] * 2


def _tone(freq: float, seconds: float) -> bytes:
    count = int(RATE * seconds)
    frames = bytearray()
    for i in range(count):
        t = i / RATE
        envelope = min(1.0, i / (RATE * 0.01)) * math.exp(-4.0 * t / seconds)
        sample = envelope * (math.sin(2 * math.pi * freq * t)
                             + 0.3 * math.sin(4 * math.pi * freq * t)) / 1.3
        frames += struct.pack("<h", int(sample * 0.6 * 32767))
    return bytes(frames)


def build_ringtone() -> bytes:
    """Return the ringtone as WAV file bytes."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        for freq, seconds in _MELODY:
            wav.writeframes(_tone(freq, seconds))
            wav.writeframes(b"\x00\x00" * int(RATE * 0.04))
    return buffer.getvalue()


_cached: bytes | None = None


def play_ringtone() -> bool:
    """Play the ringtone asynchronously. Returns False when unsupported."""
    global _cached
    if sys.platform != "win32":
        return False
    import winsound

    if _cached is None:
        _cached = build_ringtone()
    try:
        winsound.PlaySound(_cached, winsound.SND_MEMORY | winsound.SND_ASYNC)
    except RuntimeError:
        return False
    return True
