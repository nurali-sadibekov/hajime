"""Allow launching with ``python -m hajime``."""

from .app import HajimeApp


def main() -> None:
    HajimeApp().mainloop()


if __name__ == "__main__":
    main()
