"""workbuddy-computer-use: Windows desktop automation library.

Modular Python toolkit that mirrors the Codex / Hermes "computer use"
capability surface: screenshot, mouse / keyboard input, window management,
structured UI Automation lookup, image matching, and (optional) OCR.

Every public function returns plain Python objects (dicts / lists /
tuples) so callers can serialise results however they want.  The
companion :mod:`cli` module wraps these functions as a sub-command
based CLI that emits JSON to stdout for easy consumption by an LLM
agent.
"""

from . import platform_util as _platform  # noqa: F401  (re-export)
from . import screen as _screen  # noqa: F401
from . import input_control as _input_control  # noqa: F401
from . import window_mgmt as _window_mgmt  # noqa: F401
from . import ui_find as _ui_find  # noqa: F401
from . import image_match as _image_match  # noqa: F401
from . import ocr as _ocr  # noqa: F401
from . import safety as _safety  # noqa: F401

__all__ = [
    "platform",
    "screen",
    "input_control",
    "window_mgmt",
    "ui_find",
    "image_match",
    "ocr",
    "safety",
]

__version__ = "0.1.0"