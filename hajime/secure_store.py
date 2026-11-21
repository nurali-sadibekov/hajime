"""Protect small secrets (the login session) at rest.

On Windows the data is encrypted with DPAPI, so only the same Windows user on the same
machine can read it. Elsewhere the file is plain text restricted to the owner (0600).
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

MARKER = b"DPAPI1:"


def _dpapi(data: bytes, encrypt: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buffer = ctypes.create_string_buffer(data, len(data))
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = Blob()
    function = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
    args = ((ctypes.byref(source), "Hajime", None, None, None, 0, ctypes.byref(target))
            if encrypt else
            (ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)))
    if not function(*args):
        raise OSError("Windows could not process the stored session")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)


def encode(text: str) -> bytes:
    raw = text.encode("utf-8")
    if sys.platform == "win32":
        return MARKER + base64.b64encode(_dpapi(raw, True))
    return raw


def decode(blob: bytes) -> str:
    if blob.startswith(MARKER):
        return _dpapi(base64.b64decode(blob[len(MARKER):]), False).decode("utf-8")
    return blob.decode("utf-8")  # plain text: other platforms, or an older version's file


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(encode(text))
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def read(path: Path) -> str:
    return decode(path.read_bytes())
