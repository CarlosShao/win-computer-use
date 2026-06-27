"""Allow running as `python -m win_computer_use`."""

from .cli import main
import sys

if __name__ == "__main__":
    sys.exit(main())
