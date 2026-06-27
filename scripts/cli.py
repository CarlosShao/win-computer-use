"""Backward-compatible wrapper for scripts/cli.py.

This file allows existing users to continue using:
    python scripts/cli.py <command> [args...]

It imports and calls the main CLI from the win_computer_use package.
"""

import sys
import os

# Ensure the project root is in sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Import and call the main function from the package
from win_computer_use.cli import main

if __name__ == "__main__":
    sys.exit(main())
