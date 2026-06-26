"""Image matching / template-finding utilities.

Uses OpenCV's ``matchTemplate`` for sub-millisecond matching of small
template PNGs against either the full screen or a sub-region.  Useful
when an application renders to a canvas (game, Electron app with
custom widgets) where UI Automation can't reach the controls.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except ImportError as _exc:  # pragma: no cover
    raise ImportError(
        "opencv-python and numpy are required for the image_match module."
    ) from _exc

import input_control
import safety
import screen


_DEFAULT_THRESHOLD = float(os.environ.get("COMPUTER_USE_MATCH_THRESHOLD", "0.82"))


def _load_template(path: str) -> np.ndarray:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    img = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"OpenCV failed to decode template: {path}")
    return img


def _capture_for_match(
    region: Optional[Tuple[int, int, int, int]],
) -> np.ndarray:
    info = screen.screenshot(region=region, return_base64=False)
    img = cv2.imread(info["path"], cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"Failed to decode captured screenshot: {info['path']}")
    return img


def find_image(
    template_path: str,
    region: Optional[Tuple[int, int, int, int]] = None,
    threshold: float = _DEFAULT_THRESHOLD,
    *,
    max_results: int = 1,
) -> Optional[Dict[str, Any]]:
    """Locate ``template_path`` on screen.

    Returns the best match (or ``None`` when below ``threshold``).
    When ``max_results > 1`` returns a list of matches instead.
    """
    safety.check_emergency_stop()
    template = _load_template(template_path)
    haystack = _capture_for_match(region)
    result = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
    if max_results <= 1:
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < threshold:
            return None
        th, tw = template.shape[:2]
        region_off = region if region else (0, 0, haystack.shape[1], haystack.shape[0])
        return {
            "x": int(region_off[0] + max_loc[0]),
            "y": int(region_off[1] + max_loc[1]),
            "width": int(tw),
            "height": int(th),
            "confidence": float(max_val),
        }
    # Multi-result path: threshold then non-max suppression.
    locations = np.where(result >= threshold)
    matches: List[Dict[str, Any]] = []
    region_off = region if region else (0, 0, haystack.shape[1], haystack.shape[0])
    th, tw = template.shape[:2]
    for pt in zip(*locations[::-1]):
        matches.append(
            {
                "x": int(region_off[0] + pt[0]),
                "y": int(region_off[1] + pt[1]),
                "width": int(tw),
                "height": int(th),
                "confidence": float(result[pt[1], pt[0]]),
            }
        )
    # Sort by confidence desc, cap to max_results.
    matches.sort(key=lambda m: m["confidence"], reverse=True)
    return matches[:max_results]


def click_image(
    template_path: str,
    region: Optional[Tuple[int, int, int, int]] = None,
    threshold: float = _DEFAULT_THRESHOLD,
    button: str = "left",
) -> Dict[str, Any]:
    """Find a template on screen and click its centre."""
    safety.check_emergency_stop()
    match = find_image(template_path, region=region, threshold=threshold)
    if match is None:
        return {"ok": False, "error": "template not found", "template": template_path, "threshold": threshold}
    cx = match["x"] + match["width"] // 2
    cy = match["y"] + match["height"] // 2
    input_control.click(cx, cy, button=button)
    return {"ok": True, "matched": match, "clicked": {"x": cx, "y": cy, "button": button}}


def wait_for_image(
    template_path: str,
    region: Optional[Tuple[int, int, int, int]] = None,
    timeout: float = 10.0,
    interval: float = 0.5,
    threshold: float = _DEFAULT_THRESHOLD,
) -> Optional[Dict[str, Any]]:
    import time as _t

    deadline = _t.time() + max(0.1, float(timeout))
    last_err: Optional[str] = None
    while _t.time() < deadline:
        safety.check_emergency_stop()
        try:
            match = find_image(template_path, region=region, threshold=threshold)
            if match is not None:
                return match
        except Exception as exc:
            last_err = str(exc)
        _t.sleep(max(0.05, float(interval)))
    return None if last_err is None else {"error": last_err}


def count_image(
    template_path: str,
    region: Optional[Tuple[int, int, int, int]] = None,
    threshold: float = _DEFAULT_THRESHOLD,
) -> int:
    """Return how many non-overlapping matches of ``template_path`` exist on screen."""
    safety.check_emergency_stop()
    matches = find_image(template_path, region=region, threshold=threshold, max_results=50)
    if matches is None:
        return 0
    if isinstance(matches, list):
        return len(matches)
    return 1