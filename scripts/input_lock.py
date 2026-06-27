"""
Optional input lock for win-computer-use.

Blocks user mouse/keyboard input during AI operations to prevent interference.
Uses Windows Low-Level Hooks (WH_KEYBOARD_LL / WH_MOUSE_LL) via ctypes.

Features:
  - Auto-releases after timeout (default 30s, configurable)
  - Manual release via hotkey (default: ESC pressed 3x quickly)
  - Shows a fullscreen overlay with "Input locked" message
  - Graceful fallback: if hooks fail, just shows overlay warning
  - Runs hooks in a dedicated thread with message pump (required by Win32)

Usage::
  from input_lock import InputLock

  lock = InputLock(timeout=30)
  lock.acquire()
  try:
      # ... AI operation ...
  finally:
      lock.release()

  # Or as context manager:
  with InputLock(timeout=30):
      # ... AI operation ...
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import threading
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ULONG_PTR (not in ctypes.wintypes)
if ctypes.sizeof(ctypes.c_void_p) == 8:
    ULONG_PTR = ctypes.c_ulonglong
else:
    ULONG_PTR = ctypes.c_ulong

# Win32 constants
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
HC_ACTION = 0

# VK codes
VK_ESCAPE = 0x1B

# Global state
_lock_active = False
_lock_timeout = 30.0
_lock_start_time = 0.0
_esc_times: list[float] = []
_hook_thread: Optional[threading.Thread] = None
_hook_thread_id: Optional[int] = None
_overlay_win = None
_release_requested = threading.Event()

# Callback holders (prevent GC)
_kb_cb = None
_ms_cb = None
_kb_hook = None
_ms_hook = None

# Message pump constants
WM_QUIT = 0x0012
WM_APP = 0x8000
MSG_STOP = WM_APP + 1


# ---------------------------------------------------------------------------
# C structs for hook callbacks
# ---------------------------------------------------------------------------

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", ctypes.wintypes.POINT),
        ("mouseData", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


# Callback types
HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
)


# ---------------------------------------------------------------------------
# Hook callbacks (called from hook thread)
# ---------------------------------------------------------------------------

def _kb_hook_proc(nCode: int, wParam: int, lParam: int) -> int:
    global _esc_times

    if nCode == HC_ACTION and _lock_active:
        vk = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents.vkCode

        # ESC x3 quick-press → manual release
        if vk == VK_ESCAPE and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            now = time.time()
            _esc_times.append(now)
            _esc_times = [t for t in _esc_times if now - t < 2.0]
            if len(_esc_times) >= 3:
                logger.info("[input_lock] Manual release (ESC x3)")
                _request_release()
                return 0  # let this ESC through

        # Block everything else
        return 1

    # Pass through
    return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)


def _ms_hook_proc(nCode: int, wParam: int, lParam: int) -> int:
    if nCode == HC_ACTION and _lock_active:
        return 1  # block all mouse events
    return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)


# ---------------------------------------------------------------------------
# Hook thread (runs message pump)
# ---------------------------------------------------------------------------

def _hook_thread_main(timeout: float, show_overlay: bool):
    """Thread that installs hooks and runs the message pump."""
    global _lock_active, _kb_hook, _ms_hook, _kb_cb, _ms_cb
    global _overlay_win, _hook_thread_id

    _hook_thread_id = threading.get_ident()
    user32 = ctypes.windll.user32

    # Install hooks
    _kb_cb = HOOKPROC(_kb_hook_proc)
    _ms_cb = HOOKPROC(_ms_hook_proc)

    _kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _kb_cb, None, 0)
    if not _kb_hook:
        logger.error(f"[input_lock] SetWindowsHookEx keyboard failed: {ctypes.GetLastError()}")
        _request_release()
        return

    _ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, _ms_cb, None, 0)
    if not _ms_hook:
        logger.error(f"[input_lock] SetWindowsHookEx mouse failed: {ctypes.GetLastError()}")
        user32.UnhookWindowsHookEx(_kb_hook)
        _kb_hook = None
        _request_release()
        return

    _lock_active = True
    logger.info(f"[input_lock] Hooks installed (timeout={timeout}s)")

    # Show overlay in this thread (Tkinter needs to run here or in another thread)
    if show_overlay:
        _overlay_win = _create_overlay_async()

    # Message pump (required for LL hooks to work)
    msg = ctypes.wintypes.MSG()
    start_time = time.time()

    while _lock_active and not _release_requested.is_set():
        # Check timeout
        if time.time() - start_time > timeout:
            logger.warning(f"[input_lock] Timeout ({timeout}s), auto-releasing")
            break

        # Peek message (non-blocking)
        if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0x0001):  # PM_REMOVE
            if msg.message == WM_QUIT or msg.message == MSG_STOP:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        else:
            time.sleep(0.01)  # yield

    # Cleanup
    _do_release_cleanup()


def _request_release():
    """Request lock release (thread-safe)."""
    _release_requested.set()


def _do_release_cleanup():
    """Uninstall hooks and cleanup (called from hook thread)."""
    global _lock_active, _kb_hook, _ms_hook, _overlay_win

    _lock_active = False

    user32 = ctypes.windll.user32
    if _kb_hook:
        user32.UnhookWindowsHookEx(_kb_hook)
        _kb_hook = None
    if _ms_hook:
        user32.UnhookWindowsHookEx(_ms_hook)
        _ms_hook = None

    # Destroy overlay
    if _overlay_win:
        try:
            _overlay_win.quit()
        except Exception:
            pass
        try:
            _overlay_win.destroy()
        except Exception:
            pass
        _overlay_win = None

    logger.info("[input_lock] Released")


# ---------------------------------------------------------------------------
# Overlay window
# ---------------------------------------------------------------------------

def _create_overlay_async():
    """Create overlay in a new thread (Tkinter needs its own mainloop)."""
    result = []

    def _run():
        try:
            import tkinter as tk

            root = tk.Tk()
            result.append(root)

            root.attributes("-topmost", True)
            root.attributes("-fullscreen", True)
            root.attributes("-alpha", 0.3)
            root.configure(bg="black")
            root.overrideredirect(True)

            # Click-through
            try:
                hwnd = root.winfo_id()
                ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                ctypes.windll.user32.SetWindowLongW(
                    hwnd, -20, ex_style | 0x00080000 | 0x00000020
                )
            except Exception:
                pass

            frame = tk.Frame(root, bg="black")
            frame.pack(expand=True, fill="both")

            tk.Label(
                frame, text="🔒  Input Locked",
                fg="white", bg="black",
                font=("Segoe UI", 48, "bold"),
            ).pack(expand=True)

            tk.Label(
                frame,
                text="Agent is operating...   (Press ESC 3× quickly to unlock)",
                fg="#AAAAAA", bg="black",
                font=("Segoe UI", 16),
            ).pack(pady=(0, 40))

            root.update()
            root.mainloop()
        except Exception as e:
            logger.warning(f"[input_lock] Overlay error: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(0.3)  # let Tkinter init
    return result[0] if result else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class InputLock:
    """
    Context manager for input locking.

    Usage::
      with InputLock(timeout=30):
          # ... AI operation ...  (user input is blocked)

    Or manually::
      lock = InputLock(timeout=30)
      lock.acquire()
      try:
          # ...
      finally:
          lock.release()
    """

    def __init__(self, timeout: float = 30.0, show_overlay: bool = True):
        self.timeout = max(5.0, float(timeout))
        self.show_overlay = show_overlay
        self._thread: Optional[threading.Thread] = None

    def acquire(self) -> bool:
        """Acquire the input lock. Returns True on success."""
        global _hook_thread

        if _lock_active:
            logger.warning("[input_lock] Already locked")
            return False

        _release_requested.clear()

        # Check admin
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            if not is_admin:
                logger.warning(
                    "[input_lock] Not admin — lock may be incomplete. "
                    "Run as administrator for full input blocking."
                )
        except Exception:
            is_admin = False

        # Start hook thread
        self._thread = threading.Thread(
            target=_hook_thread_main,
            args=(self.timeout, self.show_overlay),
            daemon=True,
        )
        self._thread.start()

        # Wait briefly for hooks to install
        time.sleep(0.2)
        return _lock_active

    def release(self):
        """Release the input lock."""
        if _lock_active:
            _request_release()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
        return False

    @staticmethod
    def is_active() -> bool:
        return _lock_active

    @staticmethod
    def force_release():
        _request_release()


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_lock(args: object) -> int:
    """Test: lock input for N seconds."""
    import time as _time
    timeout = getattr(args, "timeout", 10)
    print(f"[input_lock] Locking input for {timeout}s...")
    print("  Press ESC 3x quickly to unlock early")
    with InputLock(timeout=timeout, show_overlay=True):
        _time.sleep(timeout)
    print("[input_lock] Released.")
    return 0


def cmd_unlock(args: object) -> int:
    """Force-release input lock."""
    InputLock.force_release()
    print("[input_lock] Force-released.")
    return 0
