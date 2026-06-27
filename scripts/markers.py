"""Semantic screenshot: detect clickable regions and draw markers.

Uses UI Automation (uiautomation) to get accessible element trees from the
FOREGROUND window (default), then draws bounding boxes + numbered labels
on the screenshot — similar to OmniParser / SeeAct.

Usage (from cli.py):
    python cli.py screenshot --with-markers --output shot_marked.png
    python cli.py screenshot --with-markers --all-windows --output full.png
"""

from __future__ import annotations

import base64
import ctypes
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except ImportError as _exc:
    raise ImportError(
        "opencv-python and numpy are required for --with-markers. "
        "Install them with `pip install opencv-python numpy`."
    ) from _exc

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except ImportError as _exc:
    raise ImportError("Pillow is required for --with-markers.") from _exc

import platform_util as _platform

# Re-use screenshot() from the screen module (same package)
from screen import screenshot as _raw_screenshot


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Control types considered "clickable" — these are worth highlighting for AI
_CLICKABLE_TYPES = {
    "Button",
    "ButtonControl",
    "Edit",
    "EditControl",
    "ComboBox",
    "ComboBoxControl",
    "ListBox",
    "ListBoxControl",
    "ListItem",
    "ListItemControl",
    "Hyperlink",
    "HyperlinkControl",
    "MenuItem",
    "MenuItemControl",
    "Menu",
    "MenuControl",
    "TabItem",
    "TabItemControl",
    "RadioButton",
    "RadioButtonControl",
    "CheckBox",
    "CheckBoxControl",
    "Slider",
    "Spinner",
    "SplitButton",
    "SplitButtonControl",
    "DataItem",
    "DataItemControl",
    "TreeItem",
    "TreeItemControl",
    "Thumb",
    "ThumbControl",
    "Custom",
    "CustomControl",
    "TitleBar",
}

# Control types that are purely structural — skip entirely (don't even record)
_HARD_SKIP_TYPES = {
    "Window",
    "WindowControl",
    "Pane",
    "PaneControl",       # most common noisy container
    "ScrollBar",
    "ScrollBarControl",
    "Separator",
    "SeparatorControl",
    "StatusBar",
    "StatusBarControl",
    "TitleBar",
    "MenuBar",
    "MenuBarControl",
    "ToolBar",
    "ToolBarControl",
    "Group",
    "GroupControl",
    "Header",
    "HeaderControl",
    "HeaderItem",
    "HeaderItemControl",
    "Table",
    "TableControl",
    "DataGrid",
    "DataGridControl",
    "List",
    "ListControl",
    "Tree",
    "TreeControl",
    "TabControl",
    "Document",
    "DocumentControl",
    "Image",
    "ImageControl",
    "Text",
    "TextControl",      # pure text labels are usually NOT clickable targets
    "ProgressBar",
    "ProgressBarControl",
}

# Window class names to skip entirely (system / background windows)
_SKIP_WINDOW_CLASSES = {
    "Program Manager",     # Desktop + icons
    "WorkerW",             # Desktop worker
    "#32769",              # Desktop root
    "Shell_TrayWnd",       # Taskbar
    "SystemTrayData",      # Notification area
}

# Regex for icon/private-use characters (e.g. "", "") — not useful text
_ICON_CHAR_RE = re.compile(
    r"^[\uE000-\uF8FF\U000F0000-\U000FFFFF\u2702-\u27B0"
    r"\u2460-\u24FF\u25A0-\u25FF\u2600-\u26FF\u2700-\u27BF]+$"
)

# ---------------------------------------------------------------------------
# Importance scoring — higher = more likely to be a useful click target for AI
# Used to filter + sort elements before drawing.
# ---------------------------------------------------------------------------
_IMPORTANCE = {
    # High-value: definitely clickable, AI should see these
    "Button":           10,
    "ButtonControl":    10,
    "SplitButton":      10,
    "SplitButtonControl": 10,
    "Hyperlink":         9,
    "HyperlinkControl":  9,
    # High-value: interactive input
    "Edit":              9,
    "EditControl":       9,
    "ComboBox":          9,
    "ComboBoxControl":   9,
    "Spinner":           8,
    "SpinnerControl":    8,
    # Medium-high: clickable navigation
    "MenuItem":          8,
    "MenuItemControl":   8,
    "TabItem":           8,
    "TabItemControl":    8,
    # Medium: selectable items
    "ListItem":          7,
    "ListItemControl":   7,
    "TreeItem":          7,
    "TreeItemControl":   7,
    "DataItem":          7,
    "DataItemControl":   7,
    # Medium-low: toggle controls
    "CheckBox":          6,
    "CheckBoxControl":   6,
    "RadioButton":       6,
    "RadioButtonControl":6,
    # Low: might be clickable custom controls
    "Custom":            4,
    "CustomControl":     4,
    "Thumb":             3,
    "ThumbControl":      3,
    # Image fallback (from contour detection)
    "region":            3,
}

# Minimum importance score to keep an element (filters out low-value noise)
_MIN_IMPORTANCE = 4

# Maximum number of elements to draw (keep screenshot readable for AI)
_MAX_ELEMENTS = 50


def _importance_score(ctrl: str, text: str, rect: Tuple[int, int, int, int]) -> int:
    """Compute importance score (higher = more valuable click target)."""
    base = _IMPORTANCE.get(ctrl, 2)  # default 2 for unknown types
    # Boost: has meaningful text
    if text and len(text) >= 2 and _is_meaningful_text(text):
        base += 1
    # Penalty: very small elements (< 25px in either dimension) — likely icons/noise
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]
    if w < 25 or h < 25:
        base -= 3
    # Penalty: huge elements (> 60% of screen) — likely containers, not targets
    # (checked later with screen dimensions)
    return max(base, 0)


def _is_meaningful_text(text: str) -> bool:
    """Check if text is human-readable and useful (not just icon chars)."""
    if not text or not text.strip():
        return False
    stripped = text.strip()
    # Skip single icon/Private Use Area chars
    if len(stripped) <= 2 and _ICON_CHAR_RE.match(stripped):
        return False
    # Check if text contains any letter/digit/CJK character
    has_printable = False
    for ch in stripped:
        cat = unicodedata.category(ch)
        if cat.startswith(('L', 'N')):  # Letter or Number
            has_printable = True
            break
        if ch in '._-+@:/\\()[]{}':
            has_printable = True
    return has_printable


# ---------------------------------------------------------------------------
# Element detection via UI Automation
# ---------------------------------------------------------------------------

def _get_foreground_elements(all_windows: bool = False) -> List[Dict[str, Any]]:
    """
    Detect clickable UI elements.

    Args:
        all_windows: If False (default), only scan the FOREGROUND window.
                     If True, scan ALL visible top-level windows.

    Returns a list of dicts::

        [{"id": 1, "text": "...", "rect": (l,t,r,b), "control": "Button"}, ...]
    """
    elements: List[Dict[str, Any]] = []
    counter = [0]
    user32 = ctypes.windll.user32

    def _should_include(ctrl_type: str, text: str, rect: Tuple[int, int, int, int]) -> bool:
        """Apply all filters to decide if an element should be included."""
        l, t, r, b = rect
        w, h = r - l, b - t

        # Size filter
        if w < 12 or h < 12 or w > 4000 or h > 4000:
            return False

        # Hard skip: structural/container types
        if ctrl_type in _HARD_SKIP_TYPES:
            return False

        # Must either be a known clickable type OR have meaningful text
        is_clickable = ctrl_type in _CLICKABLE_TYPES
        has_text = _is_meaningful_text(text)

        if not is_clickable and not has_text:
            return False

        # For non-clickable-with-text items, require reasonable text length
        if not is_clickable and has_text and len(text.strip()) < 1:
            return False

        return True

    def _add_element(ctrl_type: str, text: str, rect: Tuple[int, int, int, int]):
        """Add an element with importance scoring."""
        counter[0] += 1
        importance = _importance_score(ctrl_type, text, rect)
        elements.append({
            "id": counter[0],
            "text": text.strip()[:80],
            "rect": rect,
            "control": ctrl_type,
            "enabled": True,
            "importance": importance,
        })

    # --- Strategy 1: uiautomation (primary) ---
    try:
        import uiautomation as auto  # type: ignore

        def _walk_uia_ctrl(ctrl, depth: int = 0) -> None:
            """Walk uiautomation Control objects using native PascalCase API."""
            if depth > 30:
                return

            try:
                ctrl_type = getattr(ctrl, "ControlTypeName", "") or ""
                name = getattr(ctrl, "Name", "") or ""

                # Get bounding rectangle
                rect = None
                try:
                    br = ctrl.BoundingRectangle
                    if br and br.width() > 0 and br.height() > 0:
                        rect = (int(br.left), int(br.top), int(br.right), int(br.bottom))
                except Exception:
                    pass

                # Evaluate inclusion
                if rect and _should_include(ctrl_type, name, rect):
                    _add_element(ctrl_type, name, rect)

                # Walk children (skip heavy subtrees for known containers)
                if ctrl_type not in ("ListControl", "DataGridControl", "TableControl"):
                    try:
                        for child in ctrl.GetChildren():
                            _walk_uia_ctrl(child, depth + 1)
                    except Exception:
                        pass

            except Exception:
                pass

        root = auto.GetRootControl()

        if not all_windows:
            # --- DEFAULT: Only scan the foreground window ---
            hwnd = user32.GetForegroundWindow()
            if hwnd and hwnd != 0:

                # Get the foreground control via uiautomation's FromHandle
                try:
                    fg_ctrl = auto.ControlFromHandle(hwnd)
                    if fg_ctrl:
                        print(f"[markers] Scanning foreground window: \"{getattr(fg_ctrl,'Name','')}\" ({fg_ctrl.ControlTypeName})", flush=True)
                        _walk_uia_ctrl(fg_ctrl, depth=0)
                    else:
                        print("[marks] Could not get foreground control, falling back...", flush=True)
                except Exception as e:
                    print(f"[markers] Foreground scan error: {e}", flush=True)

                # If foreground yielded nothing, try finding by matching rect
                if not elements:
                    try:
                        fg_rect = ctypes.wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(fg_rect))
                        fw, fh = fg_rect.right - fg_rect.left, fg_rect.bottom - fg_rect.top
                        if fw > 100 and fh > 100:
                            for child in root.GetChildren():
                                try:
                                    br = child.BoundingRectangle
                                    if (br and abs(br.left - fg_rect.left) < 10 and
                                        abs(br.top - fg_rect.top) < 10 and
                                        abs(br.width() - fw) < 20):
                                        print(f"[marks] Found FG window by rect match: \"{child.Name}\"", flush=True)
                                        _walk_uia_ctrl(child, depth=0)
                                        break
                                except Exception:
                                    continue
                    except Exception:
                        pass

        else:
            # --- POWER MODE: All visible windows (skip desktop/taskbar) ---
            for child in root.GetChildren():
                try:
                    br = child.BoundingRectangle
                    if not br or br.width() < 50 or br.height() < 50:
                        continue

                    # Skip desktop / taskbar windows
                    cls_name = getattr(child, "ClassName", "") or ""
                    name = getattr(child, "Name", "") or ""
                    if (cls_name in _SKIP_WINDOW_CLASSES or
                        name == "Desktop 1" or
                        name == "Taskbar"):
                        continue

                    _walk_uia_ctrl(child, depth=0)
                except Exception:
                    continue

        if elements:
            mode_str = "all windows" if all_windows else "foreground"
            print(f"[markers] uiautomation ({mode_str}): found {len(elements)} elements", flush=True)
            return elements
        else:
            print(f"[markers] uiautomation: scanned but found 0 elements", flush=True)

    except ImportError:
        print("[markers] uiautomation: not installed", flush=True)
    except Exception as e:
        print(f"[markers] uiautomation error: {e}", file=__import__('sys').stderr, flush=True)

    # --- Strategy 2: pywinauto fallback ---
    try:
        import pywinauto  # type: ignore
        from ctypes import wintypes

        hwnd = user32.GetForegroundWindow()
        if not hwnd or hwnd == 0:
            return []

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return []

        app = pywinauto.Application(backend="uia").connect(process=int(pid.value))
        win = app.window(handle=hwnd)
        wrapper = win.wrapper_object()

        def _walk_pywinauto(elem, depth: int = 0) -> None:
            if depth > 25:
                return
            try:
                ct = str(getattr(elem, "control_type", "") or "")
                text = str(getattr(elem, "window_text", lambda: "")() or "")
                rect = None
                try:
                    r = elem.rectangle()
                    if r:
                        rect = (int(r.left), int(r.top), int(r.right), int(r.bottom))
                except Exception:
                    pass
                if rect and _should_include(ct, text, rect):
                    _add_element(ct, text, rect)
                try:
                    for child in elem.children():
                        _walk_pywinauto(child, depth + 1)
                except Exception:
                    pass
            except Exception:
                pass

        _walk_pywinauto(wrapper, depth=0)

        if elements:
            print(f"[markers] pywinauto (foreground): found {len(elements)} elements", flush=True)
            return elements

    except ImportError:
        pass
    except Exception as e:
        print(f"[markers] pywinauto error: {e}", file=__import__('sys').stderr, flush=True)

    print("[markers] UI Automation: no elements found", flush=True)
    return []


# ---------------------------------------------------------------------------
# Image-based fallback (when UI Automation returns nothing useful)
# ---------------------------------------------------------------------------

def _detect_clickable_contours(img_path: str) -> List[Dict[str, Any]]:
    """Fallback: use OpenCV to find button-like rectangular regions."""
    img = cv2.imread(img_path)
    if img is None:
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    elements: List[Dict[str, Any]] = []
    min_area = 1500   # raised threshold to reduce noise
    max_area = 200000

    for i, cnt in enumerate(contours):
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        aspect = w / max(h, 1)
        if min_area < area < max_area and 0.3 < aspect < 6.0:
            elements.append({
                "id": i + 1,
                "text": "",
                "rect": (x, y, x + w, y + h),
                "control": "region",
                "enabled": True,
            })

    elements = _nms(elements, iou_thr=0.3)
    for i, el in enumerate(elements):
        el["id"] = i + 1
    return elements


def _nms(elements: List[Dict], iou_thr: float = 0.3) -> List[Dict]:
    """Non-Maximum Suppression — importance-aware.

    When two boxes overlap:
    - If importance differs by >= 3: keep the higher-importance one, suppress the lower.
    - If importance is similar: keep larger box (more likely to be the parent).
    """
    if not elements:
        return []

    def _iou(a: Dict, b: Dict) -> float:
        l1, t1, r1, b1 = a["rect"]
        l2, t2, r2, b2 = b["rect"]
        il, it = max(l1, l2), max(t1, t2)
        ir, ib = min(r1, r2), min(b1, b2)
        if ir <= il or ib <= it:
            return 0.0
        inter = (ir - il) * (ib - it)
        a_area = (r1 - l1) * (b1 - t1)
        b_area = (r2 - l2) * (b2 - t2)
        return inter / max(a_area + b_area - inter, 1)

    # Sort: highest importance first; tie-break by area (larger = more likely parent)
    sorted_els = sorted(
        elements,
        key=lambda e: (e.get("importance", 0), (e["rect"][2] - e["rect"][0]) * (e["rect"][3] - e["rect"][1])),
        reverse=True,
    )

    keep: List[Dict] = []
    while sorted_els:
        best = sorted_els.pop(0)
        keep.append(best)
        remaining = []
        for e in sorted_els:
            iou = _iou(best, e)
            if iou < iou_thr:
                remaining.append(e)
            else:
                # Overlapping: suppress if this element's importance is much lower
                best_imp = best.get("importance", 0)
                e_imp = e.get("importance", 0)
                if e_imp < best_imp - 2:
                    # Suppress low-importance overlapping element
                    continue
                elif iou < 0.6:
                    # Mild overlap, keep both
                    remaining.append(e)
                else:
                    # High overlap + similar importance: keep larger one (already popped as best)
                    continue
        sorted_els = remaining

    return keep


def _dedup_clusters(elements: List[Dict], max_per_cluster: int = 4) -> List[Dict]:
    """Reduce clusters of highly-similar elements (e.g. file lists, conversation
    lists) by keeping only representative items.

    Strategy:
      - Group elements by (control_type, similar_size, alignment).
      - If a group has >= 8 members, keep only:
          first 3  (top of list)  +  last 1  (bottom of list / "more")
      - This tells AI "there are more items like these", without overwhelming it.
    """
    if len(elements) <= 10:
        return elements  # not enough elements to bother

    from collections import defaultdict
    groups = defaultdict(list)
    for e in elements:
        ctrl = e.get("control", "unknown")
        w = e["rect"][2] - e["rect"][0]
        h = e["rect"][3] - e["rect"][1]
        size_key = (w // 50, h // 30)
        groups[(ctrl, size_key)].append(e)

    result = []
    removed = 0
    for (ctrl, size_key), group in groups.items():
        if len(group) < 8:
            result.extend(group)
            continue

        lefts = [e["rect"][0] for e in group]
        left_spread = max(lefts) - min(lefts)
        if left_spread > 80:
            result.extend(group)
            continue

        group_sorted = sorted(group, key=lambda e: e["rect"][1])
        kept = group_sorted[:3] + [group_sorted[-1]]
        result.extend(kept)
        removed += len(group) - len(kept)

    if removed > 0:
        print(f"[markers] Cluster dedup: removed {removed} similar-list items (kept representatives)", flush=True)
    return result


# ---------------------------------------------------------------------------
# Draw markers on image
# ---------------------------------------------------------------------------

def _draw_markers(
    img_path: str,
    elements: List[Dict[str, Any]],
    output_path: str,
) -> str:
    """Draw bounding boxes + numbered labels on the screenshot."""
    img = cv2.imread(img_path)
    if img is None:
        return img_path

    img_h, img_w = img.shape[:2]
    overlay = img.copy()

    COLORS = {
        "Button": (0, 200, 80),
        "ButtonControl": (0, 200, 80),
        "Edit": (60, 160, 255),
        "EditControl": (60, 160, 255),
        "ComboBox": (60, 160, 255),
        "ComboBoxControl": (60, 160, 255),
        "Hyperlink": (180, 80, 255),
        "HyperlinkControl": (180, 80, 255),
        "ListItem": (0, 180, 220),
        "ListItemControl": (0, 180, 220),
        "CheckBox": (0, 220, 180),
        "CheckBoxControl": (0, 220, 180),
        "RadioButton": (0, 220, 180),
        "RadioButtonControl": (0, 220, 180),
        "MenuItem": (220, 180, 0),
        "MenuItemControl": (220, 180, 0),
        "TabItem": (160, 120, 220),
        "TabItemControl": (160, 120, 220),
        "TreeItem": (120, 200, 160),
        "TreeItemControl": (120, 200, 160),
        "DataItem": (140, 180, 200),
        "DataItemControl": (140, 180, 200),
        "Custom": (200, 150, 100),
        "CustomControl": (200, 150, 100),
        "SplitButton": (240, 130, 80),
        "SplitButtonControl": (240, 130, 80),
        "region": (180, 180, 180),
        "Thumb": (150, 150, 150),
        "ThumbControl": (150, 150, 150),
        "TitleBar": (100, 100, 100),
    }

    def _get_color(ctrl: str) -> Tuple[int, int, int]:
        return COLORS.get(ctrl, (200, 200, 200))

    for el in elements:
        l, t, r, b = el["rect"]
        label = str(el["id"])
        text = el.get("text", "")[:30]
        ctrl = el.get("control", "")
        color = _get_color(ctrl)

        # Clamp coordinates
        l = max(0, min(l, img_w - 1))
        t = max(0, min(t, img_h - 1))
        r = max(l + 1, min(r, img_w))
        b = max(t + 1, min(b, img_h))

        # Semi-transparent fill
        cv2.rectangle(overlay, (l, t), (r, b), color, -1)
        # White border
        cv2.rectangle(overlay, (l, t), (r, b), (255, 255, 255), 2)

        # Number label above-left
        font = cv2.FONT_HERSHEY_SIMPLEX
        fs, thick = 0.5, 1
        (tw, th), bl = cv2.getTextSize(label, font, fs, thick)
        label_y = max(t - th - 10, 0)
        label_x = max(l, 0)
        cv2.rectangle(overlay, (label_x - 2, label_y - bl - 2),
                      (label_x + tw + 4, label_y + th + 2), color, -1)
        cv2.putText(overlay, label, (label_x, label_y + th),
                     font, fs, (255, 255, 255), thick, cv2.LINE_AA)

        # Text annotation below box
        if text:
            tf_scale = 0.45
            (tw2, th2), _ = cv2.getTextSize(text, font, tf_scale, 1)
            text_y = min(b + th2 + 6, img_h - 1)
            text_x = l
            if text_x + tw2 > img_w:
                tw2 = img_w - text_x
            if text_y > img_h - 1:
                text_y = img_h - 1
            cv2.rectangle(overlay, (text_x, text_y - th2 - 2),
                          (text_x + tw2 + 2, text_y + 2), (30, 30, 30, 200), -1)
            cv2.putText(overlay, text[:40], (text_x, text_y),
                         font, tf_scale, (210, 210, 210), 1, cv2.LINE_AA)

    # Blend: light overlay so original screenshot stays visible
    result = cv2.addWeighted(img, 0.75, overlay, 0.25, 0)

    # Re-draw borders & labels fully opaque on top
    for el in elements:
        l, t, r, b = el["rect"]
        label = str(el["id"])
        text = el.get("text", "")[:30]
        ctrl = el.get("control", "")
        color = _get_color(ctrl)

        l = max(0, min(l, img_w - 1))
        t = max(0, min(t, img_h - 1))
        r = max(l + 1, min(r, img_w))
        b = max(t + 1, min(b, img_h))

        cv2.rectangle(result, (l, t), (r, b), color, 2)
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), bl = cv2.getTextSize(label, font, 0.5, 1)
        label_y = max(t - th - 8, 0)
        label_x = max(l, 0)
        cv2.rectangle(result, (label_x - 2, label_y - bl - 2),
                      (label_x + tw + 4, label_y + th + 2), color, -1)
        cv2.putText(result, label, (label_x, label_y + th),
                     font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        if text:
            tf_scale = 0.45
            (tw2, th2), _ = cv2.getTextSize(text, font, tf_scale, 1)
            text_y = min(b + th2 + 6, img_h - 1)
            cv2.putText(result, text[:40], (l, text_y),
                         font, tf_scale, (220, 220, 220), 1, cv2.LINE_AA)

    cv2.imwrite(output_path, result, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    return output_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def screenshot_with_markers(
    region: Optional[Tuple[int, int, int, int]] = None,
    output_path: Optional[str] = None,
    *,
    return_base64: bool = False,
    monitor_index: int = 0,
    all_windows: bool = False,
) -> Dict[str, Any]:
    """
    Take a screenshot and annotate clickable regions.

    Args:
        all_windows: If True, scan ALL visible windows (not just foreground).

    Returns::

        {
            "ok": true,
            "path": "shot.png",
            "width": 1920,
            "height": 1080,
            "elements": [...],
            "marked_path": "shot_marked.png",
            "element_count": N,
        }
    """
    # Step 1: raw screenshot
    raw_info = _raw_screenshot(
        region=region,
        output_path=None,
        return_base64=False,
        monitor_index=monitor_index,
    )
    raw_path = raw_info["path"]

    # Step 2: get elements from UI Automation
    mode_str = "all windows" if all_windows else "foreground"
    elements = _get_foreground_elements(all_windows=all_windows)
    print(f"[markers] UI Automation ({mode_str}): {len(elements)} raw elements", flush=True)

    # Smart fallback: if foreground mode yielded too few elements,
    # automatically retry with all-windows mode (still filtering desktop)
    if not all_windows and len(elements) <= 3:
        print("[marks] Foreground scan too sparse, trying all-windows mode...", flush=True)
        all_elements = _get_foreground_elements(all_windows=True)
        if len(all_elements) > len(elements):
            elements = all_elements
            mode_str = "all-windows (auto-fallback)"
            print(f"[markers] Auto-fallback: {len(elements)} raw elements", flush=True)

    # Step 2.5: Filter + rank elements for AI consumption
    # (a) Filter by importance
    before_filter = len(elements)
    elements = [e for e in elements if e.get("importance", 0) >= _MIN_IMPORTANCE]
    print(f"[markers] Importance filter: {before_filter} -> {len(elements)} (kept score>={_MIN_IMPORTANCE})", flush=True)

    # (b) Remove huge elements (> 60% of screen)
    sw, sh = raw_info["width"], raw_info["height"]
    before_size = len(elements)
    elements = [
        e for e in elements
        if (e["rect"][2] - e["rect"][0]) < sw * 0.6
        and (e["rect"][3] - e["rect"][1]) < sh * 0.6
    ]
    if before_size != len(elements):
        print(f"[markers] Size filter: removed {before_size - len(elements)} oversized", flush=True)

    # (c) NMS to remove overlapping duplicates
    before_nms = len(elements)
    elements = _nms(elements, iou_thr=0.35)
    if before_nms != len(elements):
        print(f"[markers] NMS: {before_nms} -> {len(elements)} (removed overlapping)", flush=True)

    # (d) Cluster dedup: reduce "wall of similar buttons" for AI
    before_cluster = len(elements)
    elements = _dedup_clusters(elements)
    if before_cluster != len(elements):
        print(f"[markers] After cluster dedup: {before_cluster} -> {len(elements)}", flush=True)

    # (e) Sort by importance, keep top _MAX_ELEMENTS
    elements = sorted(elements, key=lambda e: e.get("importance", 0), reverse=True)
    if len(elements) > _MAX_ELEMENTS:
        print(f"[markers] Limiting: {len(elements)} -> {_MAX_ELEMENTS} (top importance)", flush=True)
        elements = elements[:_MAX_ELEMENTS]

    # (e) Re-number IDs
    for i, el in enumerate(elements):
        el["id"] = i + 1

    # Step 3: fallback to image-based detection if too few elements
    if len(elements) <= 2:
        print("[markers] Too few elements, trying contour detection...", flush=True)
        fallback = _detect_clickable_contours(raw_path)
        for el in fallback:
            el["importance"] = _IMPORTANCE.get(el.get("control", "region"), 3)
        if len(fallback) > len(elements):
            elements = fallback
            elements = sorted(elements, key=lambda e: e.get("importance", 0), reverse=True)
            elements = elements[:_MAX_ELEMENTS]
            for i, el in enumerate(elements):
                el["id"] = i + 1
            print(f"[markers] Contour detection: {len(elements)} regions", flush=True)

    # Step 4: draw markers
    if output_path:
        marked_path = output_path
    else:
        p = Path(raw_path)
        marked_path = str(p.parent / f"{p.stem}_marked{p.suffix}")

    if elements:
        _draw_markers(raw_path, elements, marked_path)
        print(f"[markers] Marked image saved: {marked_path} ({len(elements)} elements)", flush=True)
    else:
        shutil.copy(raw_path, marked_path)
        print("[markers] No elements found, saved raw screenshot", flush=True)

    result: Dict[str, Any] = {
        "ok": True,
        "path": raw_path,
        "width": raw_info["width"],
        "height": raw_info["height"],
        "elements": elements,
        "marked_path": marked_path,
        "element_count": len(elements),
        "scan_mode": mode_str,
    }

    if return_base64:
        with open(marked_path, "rb") as fh:
            result["marked_base64"] = base64.b64encode(fh.read()).decode("ascii")

    return result
