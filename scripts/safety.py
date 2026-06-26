"""Safety primitives: FAILSAFE, emergency stop, rate limiting.

The single source of truth for cross-process safety state is a small
JSON file in the skill's ``logs/`` folder.  Any module can call
:func:`check_emergency_stop` to abort mid-action, and any external
process (or the user) can call :func:`emergency_stop` (via the CLI) to
trigger the abort.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

_LOCK = threading.Lock()

_DEFAULT_STATE_PATH = Path(__file__).resolve().parent.parent / "logs" / "safety_state.json"


def _state_path() -> Path:
    return Path(
        os.environ.get("COMPUTER_USE_SAFETY_FILE", str(_DEFAULT_STATE_PATH))
    )


def _read_state() -> dict:
    p = _state_path()
    if not p.exists():
        return {"emergency_stop": False, "failsafe": True}
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"emergency_stop": False, "failsafe": True}


def _write_state(state: dict) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def set_failsafe(enabled: bool) -> None:
    """Enable / disable the mouse-to-corner FAILSAFE globally."""
    with _LOCK:
        s = _read_state()
        s["failsafe"] = bool(enabled)
        _write_state(s)
    try:
        import pyautogui  # type: ignore
        pyautogui.FAILSAFE = bool(enabled)
    except Exception:
        pass


def failsafe_enabled() -> bool:
    return bool(_read_state().get("failsafe", True))


def emergency_stop() -> None:
    """Set the emergency-stop flag.  Subsequent actions will abort."""
    with _LOCK:
        s = _read_state()
        s["emergency_stop"] = True
        s["stopped_at"] = time.time()
        _write_state(s)


def clear_stop() -> None:
    with _LOCK:
        s = _read_state()
        s["emergency_stop"] = False
        s.pop("stopped_at", None)
        _write_state(s)


def is_stopped() -> bool:
    return bool(_read_state().get("emergency_stop", False))


def check_emergency_stop() -> None:
    """Raise :class:`EmergencyStop` if the user has triggered a stop."""
    if is_stopped():
        raise EmergencyStop("Emergency stop requested by user.")


class EmergencyStop(RuntimeError):
    """Raised by :func:`check_emergency_stop` when an abort is pending."""