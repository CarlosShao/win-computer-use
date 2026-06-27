"""Platform / OS detection and DPI awareness helpers.

A tiny shim so the rest of the library can stay platform-agnostic in
spirit even though this skill is Windows-only.  Calling code can
``from . import platform`` and call :func:`is_windows` /
:func:`screen_size` etc. without caring whether we are on Win10,
Win11, or (theoretically) macOS / Linux.
"""

from __future__ import annotations

import ctypes
import os
import sys
from typing import Any, Dict


def is_windows() -> bool:
    """Return ``True`` when running on a Windows kernel."""
    return sys.platform == "win32" or os.name == "nt"


def enable_dpi_awareness() -> bool:
    """Best-effort DPI awareness so screen coordinates match real pixels.

    Returns ``True`` when the call succeeded.  We try the Win10
    ``PerMonitorV2`` mode first (best fidelity) and fall back to the
    system DPI awareness flag.  Silently no-ops on non-Windows.
    """
    if not is_windows():
        return False
    try:
        # Windows 10 1607+ per-monitor V2 awareness.
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined]
        return True
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]
            return True
        except Exception:
            return False


def monitor_info() -> Dict[str, Any]:
    """Return ``{width, height, left, top, scale}`` for the primary monitor.

    Uses Win32 ``GetSystemMetrics`` for SM_CXSCREEN / SM_CYSCREEN which
    returns physical pixel counts once DPI awareness has been enabled.
    """
    if not is_windows():
        # Non-Windows: we still expose the API so unit tests don't crash.
        try:
            import pyautogui  # type: ignore
            size = pyautogui.size()
            return {"width": size.width, "height": size.height, "left": 0, "top": 0, "scale": 1.0}
        except Exception:
            return {"width": 0, "height": 0, "left": 0, "top": 0, "scale": 1.0}

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    user32.SetProcessDPIAware()
    w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return {"width": int(w), "height": int(h), "left": 0, "top": 0, "scale": 1.0}


def screen_size() -> Dict[str, int]:
    """Shortcut for ``monitor_info()`` returning just ``width`` / ``height``."""
    info = monitor_info()
    return {"width": info["width"], "height": info["height"]}


# Enable DPI awareness at import time so coordinate-dependent modules
# (pyautogui, pywinauto) operate against the same coordinate space.
_enable_dpi = enable_dpi_awareness()