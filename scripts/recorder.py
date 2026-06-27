"""
Macro Recorder for win-computer-use.

Records mouse and keyboard events, saves to JSON, and replays them.

Event format (JSON)::
  {
    "version": 1,
    "recorded_at": "2026-06-27T17:00:00",
    "events": [
      {"t": 0.0, "type": "mouse_move", "x": 500, "y": 300},
      {"t": 0.12, "type": "mouse_click", "x": 500, "y": 300, "button": "left"},
      {"t": 0.45, "type": "key_down", "key": "a"},
      {"t": 0.55, "type": "key_up", "key": "a"},
      ...
    ]
  }

Usage (CLI)::
  python cli.py record start --output macro.json
  python cli.py record play --file macro.json

Usage (API)::
  POST /record/start   -> start recording
  POST /record/stop    -> stop and save
  POST /record/play    -> replay a recorded macro
  GET  /record/status  -> check recording status
"""

from __future__ import annotations

import json
import time
import threading
import ctypes
import ctypes.wintypes
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Win32 constants
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_MOUSEMOVE = 0x0200
HC_ACTION = 0
PM_REMOVE = 0x0001
WM_QUIT = 0x0012

# ULONG_PTR
if ctypes.sizeof(ctypes.c_void_p) == 8:
    _ULONG_PTR = ctypes.c_ulonglong
else:
    _ULONG_PTR = ctypes.c_ulong


# ---------------------------------------------------------------------------
# C structs
# ---------------------------------------------------------------------------

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", ctypes.wintypes.POINT),
        ("mouseData", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


# ---------------------------------------------------------------------------
# VK code -> human-readable key name
# ---------------------------------------------------------------------------

_VK_MAP = {
    0x01: "mouse_left", 0x02: "mouse_right", 0x03: "mouse_middle",
    0x08: "backspace", 0x09: "tab", 0x0D: "enter",
    0x10: "shift", 0x11: "ctrl", 0x12: "alt",
    0x1B: "escape", 0x20: "space",
    0x21: "pageup", 0x22: "pagedown", 0x23: "end", 0x24: "home",
    0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down",
    0x2D: "insert", 0x2E: "delete",
    0x30: "0", 0x31: "1", 0x32: "2", 0x33: "3",
    0x34: "4", 0x35: "5", 0x36: "6", 0x37: "7",
    0x38: "8", 0x39: "9",
    0x41: "a", 0x42: "b", 0x43: "c", 0x44: "d", 0x45: "e",
    0x46: "f", 0x47: "g", 0x48: "h", 0x49: "i", 0x4A: "j",
    0x4B: "k", 0x4C: "l", 0x4D: "m", 0x4E: "n", 0x4F: "o",
    0x50: "p", 0x51: "q", 0x52: "r", 0x53: "s", 0x54: "t",
    0x55: "u", 0x56: "v", 0x57: "w", 0x58: "x", 0x59: "y", 0x5A: "z",
    0x5B: "win",
    0x60: "numpad_0", 0x61: "numpad_1", 0x62: "numpad_2",
    0x63: "numpad_3", 0x64: "numpad_4", 0x65: "numpad_5",
    0x66: "numpad_6", 0x67: "numpad_7", 0x68: "numpad_8", 0x69: "numpad_9",
    0x70: "f1", 0x71: "f2", 0x72: "f3", 0x73: "f4",
    0x74: "f5", 0x75: "f6", 0x76: "f7", 0x77: "f8",
    0x78: "f9", 0x79: "f10", 0x7A: "f11", 0x7B: "f12",
    0x90: "numlock", 0x91: "scrolllock",
}


def _vk_to_name(vk: int) -> str:
    return _VK_MAP.get(vk, f"vk_{hex(vk)}")


# ---------------------------------------------------------------------------
# Global recorder state
# ---------------------------------------------------------------------------

_recording = False
_recording_start = 0.0
_events: List[Dict[str, Any]] = []
_record_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_last_move_t = 0.0  # throttle mouse moves

# Hook handles
_kb_hook = None
_ms_hook = None
_kb_cb = None
_ms_cb = None


# ---------------------------------------------------------------------------
# Hook callbacks
# ---------------------------------------------------------------------------

def _kb_hook_proc(nCode: int, wParam: int, lParam: int) -> int:
    global _events
    if _recording and nCode == HC_ACTION:
        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk = kb.vkCode
        key_name = _vk_to_name(vk)
        t = round(time.time() - _recording_start, 4)
        if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            _events.append({"t": t, "type": "key_down", "key": key_name})
        elif wParam in (WM_KEYUP, WM_SYSKEYUP):
            _events.append({"t": t, "type": "key_up", "key": key_name})
    return 0  # pass through


def _ms_hook_proc(nCode: int, wParam: int, lParam: int) -> int:
    global _events, _last_move_t
    if _recording and nCode == HC_ACTION:
        ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        x, y = ms.pt.x, ms.pt.y
        t = round(time.time() - _recording_start, 4)

        if wParam == WM_LBUTTONDOWN:
            _events.append({"t": t, "type": "mouse_down", "x": x, "y": y, "button": "left"})
        elif wParam == WM_LBUTTONUP:
            _events.append({"t": t, "type": "mouse_up", "x": x, "y": y, "button": "left"})
        elif wParam == WM_RBUTTONDOWN:
            _events.append({"t": t, "type": "mouse_down", "x": x, "y": y, "button": "right"})
        elif wParam == WM_RBUTTONUP:
            _events.append({"t": t, "type": "mouse_up", "x": x, "y": y, "button": "right"})
        elif wParam == WM_MBUTTONDOWN:
            _events.append({"t": t, "type": "mouse_down", "x": x, "y": y, "button": "middle"})
        elif wParam == WM_MBUTTONUP:
            _events.append({"t": t, "type": "mouse_up", "x": x, "y": y, "button": "middle"})
        elif wParam == WM_MOUSEWHEEL:
            delta = ms.mouseData >> 16
            _events.append({"t": t, "type": "mouse_wheel", "x": x, "y": y, "delta": delta})
        elif wParam == WM_MOUSEMOVE:
            if t - _last_move_t > 0.03:
                _events.append({"t": t, "type": "mouse_move", "x": x, "y": y})
                _last_move_t = t

    return 0  # pass through


# ---------------------------------------------------------------------------
# Hook thread (runs message pump)
# ---------------------------------------------------------------------------

def _hook_thread_main():
    global _recording, _kb_hook, _ms_hook, _kb_cb, _ms_cb

    user32 = ctypes.windll.user32

    HOOKPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
    )

    _kb_cb = HOOKPROC(_kb_hook_proc)
    _ms_cb = HOOKPROC(_ms_hook_proc)

    _kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _kb_cb, None, 0)
    if not _kb_hook:
        logger.error(f"[recorder] Keyboard hook failed: {ctypes.GetLastError()}")
        return

    _ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, _ms_cb, None, 0)
    if not _ms_hook:
        logger.error(f"[recorder] Mouse hook failed: {ctypes.GetLastError()}")
        user32.UnhookWindowsHookEx(_kb_hook)
        _kb_hook = None
        return

    _recording = True
    print("[recorder] Recording... (Ctrl+Escape to stop)")

    # Message pump
    msg = ctypes.wintypes.MSG()
    while _recording and not _stop_event.is_set():
        if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            if msg.message == WM_QUIT:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        else:
            time.sleep(0.01)

    _cleanup_hooks()
    print(f"[recorder] Stopped ({len(_events)} events)")


def _cleanup_hooks():
    global _kb_hook, _ms_hook
    user32 = ctypes.windll.user32
    if _kb_hook:
        user32.UnhookWindowsHookEx(_kb_hook)
        _kb_hook = None
    if _ms_hook:
        user32.UnhookWindowsHookEx(_ms_hook)
        _ms_hook = None


# ---------------------------------------------------------------------------
# Public API: Recording
# ---------------------------------------------------------------------------

def start_recording() -> bool:
    """Start recording mouse and keyboard events."""
    global _events, _recording_start, _record_thread, _stop_event

    if _recording:
        return False

    _events = []
    _stop_event.clear()
    _recording_start = time.time()

    _record_thread = threading.Thread(target=_hook_thread_main, daemon=True)
    _record_thread.start()
    time.sleep(0.2)
    return True


def stop_recording(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Stop recording and optionally save to file."""
    global _recording, _events, _stop_event

    if not _recording:
        return {"ok": False, "error": "Not recording"}

    _recording = False
    _stop_event.set()

    if _record_thread and _record_thread.is_alive():
        _record_thread.join(timeout=2.0)

    result = {
        "ok": True,
        "event_count": len(_events),
        "duration": round(time.time() - _recording_start, 2),
    }

    if output_path:
        save_recording(output_path)
        result["file"] = output_path

    return result


def save_recording(path: str) -> bool:
    """Save recorded events to JSON file."""
    data = {
        "version": 1,
        "recorded_at": datetime.now().isoformat(),
        "duration": round(time.time() - _recording_start, 2),
        "event_count": len(_events),
        "events": _events,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"[recorder] Saved {len(_events)} events to {path}")
        return True
    except Exception as e:
        logger.error(f"[recorder] Save failed: {e}")
        return False


def load_recording(path: str) -> Optional[Dict[str, Any]]:
    """Load a recording from JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[recorder] Load failed: {e}")
        return None


def is_recording() -> bool:
    return _recording


# ---------------------------------------------------------------------------
# Public API: Playback
# ---------------------------------------------------------------------------

def play_recording(path: str, speed: float = 1.0) -> Dict[str, Any]:
    """
    Play back a recorded macro.
    speed: 1.0 = original, 2.0 = 2x faster.
    """
    import pyautogui

    data = load_recording(path)
    if not data:
        return {"ok": False, "error": "Failed to load recording"}

    events = data.get("events", [])
    if not events:
        return {"ok": False, "error": "No events"}

    print(f"[recorder] Playing {len(events)} events (speed={speed}x)...")
    start = time.time()
    last_t = 0.0

    for evt in events:
        target_t = evt["t"] / speed
        elapsed = time.time() - start
        wait = target_t - elapsed
        if wait > 0.001:
            time.sleep(wait)
        try:
            _replay_event(evt, pyautogui)
        except Exception as e:
            logger.warning(f"[recorder] Replay error: {e}")

    result = {
        "ok": True,
        "events_replayed": len(events),
        "duration": round(time.time() - start, 2),
    }
    print(f"[recorder] Done ({result['duration']}s)")
    return result


def _replay_event(evt: Dict[str, Any], pg):
    t = evt["type"]
    if t == "mouse_move":
        pg.moveTo(evt["x"], evt["y"], duration=0.01)
    elif t == "mouse_down":
        pg.mouseDown(button=evt.get("button", "left"), x=evt["x"], y=evt["y"])
    elif t == "mouse_up":
        pg.mouseUp(button=evt.get("button", "left"), x=evt["x"], y=evt["y"])
    elif t == "mouse_wheel":
        d = evt.get("delta", 0)
        pg.scroll(max(1, abs(d) // 120) * (1 if d > 0 else -1))
    elif t == "key_down":
        pg.keyDown(evt["key"])
    elif t == "key_up":
        pg.keyUp(evt["key"])


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_record_start(args: object) -> int:
    import time as _t
    output = getattr(args, "output", None)
    duration = getattr(args, "duration", None)
    ok = start_recording()
    if not ok:
        print("[recorder] Failed to start")
        return 1
    if duration:
        print(f"[recorder] Auto-stopping after {duration}s...")
        _t.sleep(duration)
        print(stop_recording(output))
    else:
        try:
            while is_recording():
                _t.sleep(0.5)
        except KeyboardInterrupt:
            print(stop_recording(output))
    return 0


def cmd_record_stop(args: object) -> int:
    output = getattr(args, "output", None)
    print(stop_recording(output))
    return 0


def cmd_record_play(args: object) -> int:
    path = getattr(args, "file", None)
    speed = getattr(args, "speed", 1.0)
    if not path:
        print("[recorder] --file required")
        return 1
    print(play_recording(path, speed=speed))
    return 0
