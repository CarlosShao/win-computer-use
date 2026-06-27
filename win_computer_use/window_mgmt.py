"""Window enumeration + management.

Implemented with :mod:`pywinauto` (high-level) and :mod:`pygetwindow`
(low-level ``EnumWindows``-based queries) so we can both list every
visible top-level window *and* drive native operations like
``SetForegroundWindow`` reliably.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

try:
    import pygetwindow as gw  # type: ignore
except ImportError as _exc:  # pragma: no cover
    raise ImportError("pygetwindow is required for window_mgmt.") from _exc

try:
    from pywinauto import Application  # type: ignore
except ImportError:  # pragma: no cover - allowed optional
    Application = None  # type: ignore

from . import safety


def _safe_rect(win) -> Dict[str, int]:
    try:
        box = win.left, win.top, win.right, win.bottom
    except Exception:
        return {"left": 0, "top": 0, "right": 0, "bottom": 0, "width": 0, "height": 0}
    return {
        "left": int(box[0]),
        "top": int(box[1]),
        "right": int(box[2]),
        "bottom": int(box[3]),
        "width": int(box[2] - box[0]),
        "height": int(box[3] - box[1]),
    }


def list_windows(
    title_filter: Optional[str] = None,
    visible_only: bool = True,
    regex: bool = False,
) -> List[Dict[str, Any]]:
    """Return all top-level windows matching ``title_filter``.

    Parameters
    ----------
    title_filter:
        Optional substring (or regex when ``regex=True``) to filter by
        window title.  Case-insensitive.
    visible_only:
        When ``True`` we skip fully hidden / minimised windows.
    regex:
        Treat ``title_filter`` as a regular expression.
    """
    matcher = None
    if title_filter:
        if regex:
            matcher = re.compile(title_filter, re.IGNORECASE)
        else:
            needle = title_filter.lower()
            matcher = lambda t: needle in t.lower()  # noqa: E731

    out: List[Dict[str, Any]] = []
    for title in gw.getAllTitles():
        if matcher:
            if hasattr(matcher, 'search'):
                # regex matcher
                if not matcher.search(title):
                    continue
            else:
                # lambda matcher
                if not matcher(title):
                    continue
        try:
            wins = gw.getWindowsWithTitle(title)
        except Exception:
            continue
        for w in wins:
            try:
                visible = bool(w.visible) if hasattr(w, "visible") else True
            except Exception:
                visible = True
            if visible_only and not visible:
                continue
            out.append(
                {
                    "title": title,
                    "handle": int(w._hWnd) if hasattr(w, "_hWnd") else 0,
                    "pid": int(w.pid) if hasattr(w, "pid") else 0,
                    "visible": visible,
                    "rect": _safe_rect(w),
                }
            )
    # De-duplicate windows reported under multiple title variants.
    seen = set()
    uniq = []
    for item in out:
        key = (item["handle"], item["title"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq


def find_window(
    title: Optional[str] = None,
    pid: Optional[int] = None,
    handle: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Look up a single window by title / pid / handle."""
    if handle is not None:
        try:
            w = gw.Window(handle)
            return {
                "title": w.title,
                "handle": int(w._hWnd) if hasattr(w, "_hWnd") else int(handle),
                "pid": int(w.pid) if hasattr(w, "pid") else 0,
                "rect": _safe_rect(w),
            }
        except Exception:
            return None
    if pid is not None:
        for entry in list_windows():
            if entry["pid"] == pid:
                return entry
        return None
    if title is None:
        return None
    wins = gw.getWindowsWithTitle(title)
    if not wins:
        return None
    w = wins[0]
    return {
        "title": w.title,
        "handle": int(w._hWnd) if hasattr(w, "_hWnd") else 0,
        "pid": int(w.pid) if hasattr(w, "pid") else 0,
        "rect": _safe_rect(w),
    }


def activate_window(
    title: Optional[str] = None,
    handle: Optional[int] = None,
    pid: Optional[int] = None,
) -> Dict[str, Any]:
    """Bring the matching window to the foreground.

    Returns ``{"ok": True, "window": {...}}`` on success or
    ``{"ok": False, "error": ...}`` when the window could not be
    located / activated.  Foreground activation on Windows requires the
    foreground-lock privilege; we fall back to ``ShowWindow`` /
    ``SetWindowPos`` after :func:`SetForegroundWindow` to maximise
    reliability when the calling process is not the active one.
    """
    safety.check_emergency_stop()
    import ctypes

    info = find_window(title=title, handle=handle, pid=pid)
    if info is None:
        return {"ok": False, "error": "window not found", "title": title, "handle": handle, "pid": pid}
    hwnd = info["handle"]
    if not hwnd:
        return {"ok": False, "error": "window has no handle", "window": info}

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    SW_RESTORE = 9
    SW_SHOW = 5
    HWND_TOP = 0
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001

    # Try a normal restore + foreground sequence.
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.ShowWindow(hwnd, SW_SHOW)
    user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.05)
    info["activated"] = True
    return {"ok": True, "window": info}


def minimize_window(title=None, handle=None, pid=None) -> Dict[str, Any]:
    return _win_cmd(0xF020, title=title, handle=handle, pid=pid)  # SC_MINIMIZE


def maximize_window(title=None, handle=None, pid=None) -> Dict[str, Any]:
    return _win_cmd(0xF030, title=title, handle=handle, pid=pid)  # SC_MAXIMIZE


def restore_window(title=None, handle=None, pid=None) -> Dict[str, Any]:
    return _win_cmd(0xF120, title=title, handle=handle, pid=pid)  # SC_RESTORE


def close_window(title=None, handle=None, pid=None) -> Dict[str, Any]:
    return _win_cmd(0xF060, title=title, handle=handle, pid=pid)  # SC_CLOSE


def _win_cmd(syscommand: int, title=None, handle=None, pid=None) -> Dict[str, Any]:
    """Send a WM_SYSCOMMAND via :func:`SendMessage` to a window handle."""
    import ctypes

    info = find_window(title=title, handle=handle, pid=pid)
    if info is None:
        return {"ok": False, "error": "window not found"}
    hwnd = info["handle"]
    if not hwnd:
        return {"ok": False, "error": "window has no handle"}
    WM_SYSCOMMAND = 0x0112
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    user32.SendMessageW(hwnd, WM_SYSCOMMAND, syscommand, 0)
    return {"ok": True, "window": info}


def window_rect(title=None, handle=None, pid=None) -> Dict[str, int]:
    info = find_window(title=title, handle=handle, pid=pid)
    if info is None:
        return {"left": 0, "top": 0, "right": 0, "bottom": 0, "width": 0, "height": 0}
    return info["rect"]