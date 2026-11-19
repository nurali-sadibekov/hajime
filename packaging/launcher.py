"""Entry script for frozen (PyInstaller) builds."""

import sys

from hajime.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
