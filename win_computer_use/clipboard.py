"""Windows clipboard access via ctypes (no dependencies).

Provides fast text read/write to the Windows clipboard using direct Win32 API calls.
No external packages needed — pure ctypes.
"""

from __future__ import annotations

import ctypes

# Constants
CF_UNICODETEXT = 13

# Load Windows DLLs and set proper 64-bit types for pointer safety
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_kernel32.GlobalAlloc.restype = ctypes.c_void_p
_kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalSize.restype = ctypes.c_size_t
_kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
_kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalFree.argtypes = [ctypes.c_void_p]

_user32.GetClipboardData.restype = ctypes.c_void_p
_user32.GetClipboardData.argtypes = [ctypes.c_uint]
_user32.SetClipboardData.restype = ctypes.c_void_p
_user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]


def get_text() -> str:
    """Read Unicode text from the Windows clipboard.

    Returns empty string if clipboard is empty or doesn't contain text.
    """
    if not _user32.OpenClipboard(None):
        return ""

    try:
        handle = _user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""

        ptr = _kernel32.GlobalLock(handle)
        if not ptr:
            return ""

        try:
            # wstring_at reads wide string until null terminator
            return ctypes.wstring_at(ptr)
        finally:
            _kernel32.GlobalUnlock(handle)
    finally:
        _user32.CloseClipboard()


def set_text(text: str) -> bool:
    """Write Unicode text to the Windows clipboard.

    Returns True on success, False on failure.
    """
    if not text:
        return False

    if not _user32.OpenClipboard(None):
        return False

    try:
        _user32.EmptyClipboard()

        # Allocate fixed memory with null terminator
        byte_size = (len(text) + 1) * 2  # 2 bytes per wchar_t
        handle = _kernel32.GlobalAlloc(0, byte_size)
        if not handle:
            return False

        try:
            encoded = text.encode("utf-16-le")
            ctypes.memmove(handle, encoded, len(encoded))
            # Null terminator (2 zero bytes)
            ctypes.memset(handle + len(encoded), 0, 2)
        except Exception:
            _kernel32.GlobalFree(handle)
            return False

        # SetClipboardData takes ownership of handle
        _user32.SetClipboardData(CF_UNICODETEXT, handle)
        return True
    finally:
        _user32.CloseClipboard()
