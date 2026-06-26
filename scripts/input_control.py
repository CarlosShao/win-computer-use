"""Mouse + keyboard input primitives.

Built on top of :mod:`pyautogui`, which on Windows wraps ``SendInput``
under the hood.  ``pyautogui``'s built-in ``FAILSAFE`` (mouse to the
top-left corner aborts) is left enabled by default.  Callers wanting to
override that should go through :func:`safety.set_failsafe` rather than
mutating the global directly.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, Optional

try:
    import pyautogui  # type: ignore
except ImportError as _exc:  # pragma: no cover
    raise ImportError("pyautogui is required for the input_control module.") from _exc

from . import safety

# A small default to make double-clicks feel snappy without skipping.
pyautogui.PAUSE = 0.02  # type: ignore[attr-defined]
pyautogui.FAILSAFE = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Mouse
# ---------------------------------------------------------------------------


def mouse_position() -> Dict[str, int]:
    """Return ``{x, y}`` of the current cursor position."""
    x, y = pyautogui.position()  # type: ignore[arg-type]
    return {"x": int(x), "y": int(y)}


def move_to(x: int, y: int, duration: float = 0.0) -> Dict[str, Any]:
    """Move the cursor smoothly (or instantly when ``duration`` is 0)."""
    safety.check_emergency_stop()
    pyautogui.moveTo(int(x), int(y), duration=max(0.0, float(duration)))
    return {"x": int(x), "y": int(y)}


def click(
    x: int,
    y: int,
    button: str = "left",
    clicks: int = 1,
    interval: float = 0.05,
) -> Dict[str, Any]:
    """Click ``(x, y)`` once or multiple times."""
    safety.check_emergency_stop()
    btn = button.lower()
    if btn not in {"left", "right", "middle"}:
        raise ValueError(f"button must be one of left/right/middle, got {button!r}")
    pyautogui.click(  # type: ignore[call-overload]
        x=int(x),
        y=int(y),
        button=btn,  # type: ignore[arg-type]
        clicks=int(clicks),
        interval=float(interval),
    )
    return {"x": int(x), "y": int(y), "button": btn, "clicks": int(clicks)}


def double_click(x: int, y: int) -> Dict[str, Any]:
    return click(x, y, button="left", clicks=2, interval=0.08)


def right_click(x: int, y: int) -> Dict[str, Any]:
    return click(x, y, button="right", clicks=1)


def drag(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    duration: float = 0.3,
    button: str = "left",
) -> Dict[str, Any]:
    """Drag from ``(x1, y1)`` to ``(x2, y2)``."""
    safety.check_emergency_stop()
    pyautogui.moveTo(int(x1), int(y1))
    pyautogui.dragTo(  # type: ignore[attr-defined]
        int(x2),
        int(y2),
        duration=max(0.05, float(duration)),
        button=button,  # type: ignore[arg-type]
    )
    return {"from": [int(x1), int(y1)], "to": [int(x2), int(y2)]}


def scroll(clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
    """Scroll the mouse wheel by ``clicks`` (positive = up)."""
    safety.check_emergency_stop()
    if x is None or y is None:
        cx, cy = pyautogui.position()  # type: ignore[misc]
    else:
        cx, cy = int(x), int(y)
    pyautogui.scroll(int(clicks), x=cx, y=cy)  # type: ignore[call-arg]
    return {"x": int(cx), "y": int(cy), "clicks": int(clicks)}


# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------


def type_text(text: str, interval: float = 0.02) -> Dict[str, Any]:
    """Type ``text`` using Unicode-aware ``typewrite``.

    For long or non-ASCII text we fall back to clipboard paste via
    ``pyperclip`` (when available) because ``pyautogui.typewrite`` only
    handles the basic ASCII printable range reliably.
    """
    safety.check_emergency_stop()
    n = len(text)
    if n == 0:
        return {"typed": 0}
    # Fast path for short ASCII.
    if n <= 200 and all(ord(c) < 128 and c.isprintable() or c in "\n\r\t" for c in text):
        pyautogui.typewrite(text, interval=max(0.0, float(interval)))  # type: ignore[arg-type]
        return {"typed": n, "mode": "typewrite"}
    # Long / non-ASCII path: use clipboard.
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(text)
        hotkey("ctrl", "v")
        return {"typed": n, "mode": "clipboard"}
    except Exception:
        # Last resort: try typewrite anyway, accept that some chars may drop.
        pyautogui.typewrite(text, interval=max(0.0, float(interval)))  # type: ignore[arg-type]
        return {"typed": n, "mode": "typewrite-fallback"}


def hotkey(*keys: str) -> Dict[str, Any]:
    """Press a chord such as ``ctrl+c``.  Order matters for modifiers."""
    safety.check_emergency_stop()
    if not keys:
        return {"keys": []}
    pyautogui.hotkey(*keys)  # type: ignore[arg-type]
    return {"keys": list(keys)}


def key_press(key: str) -> Dict[str, Any]:
    """Press and release a single key (e.g. ``"enter"`` or ``"f5"``)."""
    safety.check_emergency_stop()
    pyautogui.press(key)  # type: ignore[arg-type]
    return {"key": key}


def key_down(key: str) -> Dict[str, Any]:
    safety.check_emergency_stop()
    pyautogui.keyDown(key)  # type: ignore[arg-type]
    return {"key": key, "state": "down"}


def key_up(key: str) -> Dict[str, Any]:
    pyautogui.keyUp(key)  # type: ignore[arg-type]
    return {"key": key, "state": "up"}


def wait(seconds: float) -> Dict[str, Any]:
    """Sleep for ``seconds`` seconds (always checked against the emergency stop)."""
    end = time.time() + max(0.0, float(seconds))
    while time.time() < end:
        safety.check_emergency_stop()
        time.sleep(min(0.05, end - time.time()))
    return {"seconds": float(seconds)}