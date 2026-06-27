"""Screenshot primitives built on top of :mod:`mss` (fastest pure-Python option).

We deliberately do not use ``pyautogui.screenshot`` because it shells
out to ``PIL.ImageGrab`` which is significantly slower on multi-monitor
setups.  ``mss`` captures via direct Win32 BitBlt and is roughly 3-5x
faster.
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import mss  # type: ignore
    import mss.tools  # type: ignore
except ImportError as _exc:  # pragma: no cover - hard dependency
    raise ImportError(
        "mss is required for the screen module. "
        "Install it with `pip install mss`."
    ) from _exc

try:
    from PIL import Image  # type: ignore
except ImportError as _exc:  # pragma: no cover
    raise ImportError("Pillow is required for the screen module.") from _exc

from . import platform_util as _platform


# Default output directory (overridable via env var COMPUTER_USE_SCREENSHOT_DIR).
_DEFAULT_DIR = Path(
    os.environ.get(
        "COMPUTER_USE_SCREENSHOT_DIR",
        str(Path(__file__).resolve().parent.parent / "screenshots"),
    )
)


def _ensure_dir(path: Optional[Path]) -> Path:
    out = Path(path) if path else _DEFAULT_DIR
    out.mkdir(parents=True, exist_ok=True)
    return out


def _region_to_mss(region: Optional[Tuple[int, int, int, int]]) -> Dict[str, int]:
    """Normalise a ``(left, top, width, height)`` tuple to mss's dict shape."""
    if region is None:
        return {"left": 0, "top": 0, "width": 0, "height": 0}
    left, top, width, height = region
    return {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}


def screenshot(
    region: Optional[Tuple[int, int, int, int]] = None,
    output_path: Optional[str] = None,
    *,
    return_base64: bool = False,
    monitor_index: int = 0,
) -> Dict[str, Any]:
    """Capture a screenshot.

    Parameters
    ----------
    region:
        Optional ``(left, top, width, height)`` tuple to capture only a
        sub-rectangle of the primary monitor.
    output_path:
        Where to write the PNG.  When omitted we auto-generate a path
        under :data:`_DEFAULT_DIR` with a timestamp suffix.
    return_base64:
        When ``True`` we include the PNG as a base64 string in the
        returned dict.  Useful for piping directly into a vision model.
    monitor_index:
        Which monitor to capture (0-based).  Ignored when ``region`` is
        provided.
    """
    out_dir = _ensure_dir(None if output_path else None)
    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out_file = out_dir / f"shot-{stamp}-{int(time.time() * 1000) % 1000:03d}.png"

    with mss.mss() as sct:
        monitors = sct.monitors
        if region is not None:
            grab = sct.grab(_region_to_mss(region))
            width = int(grab.size[0])
            height = int(grab.size[1])
        else:
            if monitor_index >= len(monitors):
                monitor_index = 0
            mon = monitors[monitor_index]
            grab = sct.grab(mon)
            width = int(grab.size[0])
            height = int(grab.size[1])
        mss.tools.to_png(grab.rgb, grab.size, output=str(out_file))

    result: Dict[str, Any] = {
        "path": str(out_file),
        "width": width,
        "height": height,
        "bytes": out_file.stat().st_size,
    }
    if return_base64:
        with open(out_file, "rb") as fh:
            result["base64"] = base64.b64encode(fh.read()).decode("ascii")
    return result


def pixel_color(x: int, y: int) -> Dict[str, int]:
    """Return ``{r, g, b}`` for the pixel at ``(x, y)``."""
    with mss.mss() as sct:
        # 1x1 grab around the requested pixel.
        grab = sct.grab({"left": int(x), "top": int(y), "width": 1, "height": 1})
        pixel = grab.pixel(0, 0)
    return {"r": int(pixel[0]), "g": int(pixel[1]), "b": int(pixel[2])}


def screen_size() -> Dict[str, int]:
    """Return ``{width, height}`` of the primary monitor."""
    return _platform.screen_size()