"""Command-line entry point: ``python -m hajime`` or the ``hajime`` command."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from logging.handlers import RotatingFileHandler

from . import __version__, storage


def _configure_logging() -> None:
    """Log unexpected errors to a file next to the user data (best effort)."""
    log_path = storage.default_data_path().with_name("hajime.log")
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path, maxBytes=256_000, backupCount=1,
            encoding="utf-8", delay=True,
        )
    except OSError:
        return
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger("hajime").addHandler(handler)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in {"-V", "--version"}:
        print(f"hajime {__version__}")
        return 0

    _configure_logging()
    from .app import HajimeApp  # imported late so --version works without a display

    try:
        app = HajimeApp()
    except tk.TclError as error:
        print(f"Hajime could not open a window: {error}", file=sys.stderr)
        return 1
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
