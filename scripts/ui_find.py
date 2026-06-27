"""Structured UI Automation lookup.

Wraps :mod:`pywinauto`'s ``UIA backend`` so callers can find buttons,
edit boxes, list items, and other Win32 / WinForms / WPF / Qt / Electron
controls by ``auto_id``, ``control_type``, ``name`` (display text), or
``class_name`` -- without resorting to coordinate-based blind clicks.

This is *much* more robust than pixel-clicking on apps that reflow or
localise their UI.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

try:
    from pywinauto import Application  # type: ignore
    from pywinauto.findwindows import ElementNotFoundError  # type: ignore
except ImportError as _exc:  # pragma: no cover
    raise ImportError("pywinauto is required for the ui_find module.") from _exc

import safety
import window_mgmt

_CONTROL_TYPES = {
    "Button",
    "Edit",
    "CheckBox",
    "RadioButton",
    "ComboBox",
    "List",
    "ListItem",
    "Menu",
    "MenuItem",
    "Tab",
    "TabItem",
    "Text",
    "Tree",
    "TreeItem",
    "Window",
    "Hyperlink",
    "Spinner",
    "ProgressBar",
    "ScrollBar",
    "Slider",
    "StatusBar",
    "ToolBar",
    "ToolTip",
    "Calendar",
    "DataGrid",
    "DataItem",
    "Document",
    "Group",
    "Header",
    "HeaderItem",
    "Image",
    "Pane",
    "Separator",
    "SplitButton",
    "Table",
    "Thumb",
    "TitleBar",
}


def _build_criteria(
    auto_id: Optional[str] = None,
    control_type: Optional[str] = None,
    name: Optional[str] = None,
    class_name: Optional[str] = None,
    regex_name: bool = False,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    criteria: Dict[str, Any] = {}
    if title is not None:
        criteria["title"] = title
    if auto_id:
        criteria["auto_id"] = auto_id
    if control_type:
        ct = control_type if control_type.endswith("Control") else control_type
        # pywinauto UIA backend accepts control_type like "Button".
        criteria["control_type"] = control_type
    if name:
        criteria["name"] = name
    if class_name:
        criteria["class_name"] = class_name
    if regex_name:
        criteria["found_index"] = 0  # placeholder; UIAdv3 uses predicate
    return criteria


def _attach_window(window: Dict[str, Any]):
    """Attach a :class:`pywinauto.Application` to an already-running window."""
    handle = window.get("handle")
    pid = window.get("pid")
    if handle and int(handle) > 0:
        app = Application(backend="uia").connect(handle=int(handle))
    elif pid and int(pid) > 0:
        app = Application(backend="uia").connect(process=int(pid))
    else:
        raise RuntimeError("Window has no handle or pid; cannot attach.")
    return app


def _resolve_app(window: Optional[Dict[str, Any]]):
    if window is None:
        raise RuntimeError("Window descriptor required.")
    return _attach_window(window)


def find_element(
    title: Optional[str] = None,
    handle: Optional[int] = None,
    pid: Optional[int] = None,
    *,
    auto_id: Optional[str] = None,
    control_type: Optional[str] = None,
    name: Optional[str] = None,
    class_name: Optional[str] = None,
    regex_name: bool = False,
    index: int = 0,
) -> Optional[Dict[str, Any]]:
    """Return a serialisable descriptor for the first matching UI element.

    All filter parameters are optional but at least one is required
    (otherwise we'd return the root window every time).  Returns
    ``None`` when no element matches.
    """
    safety.check_emergency_stop()
    if not any([auto_id, control_type, name, class_name]):
        raise ValueError(
            "find_element requires at least one of auto_id / control_type / name / class_name."
        )
    window = window_mgmt.find_window(title=title, handle=handle, pid=pid)
    if window is None:
        return None
    app = _resolve_app(window)
    dlg = app.window(handle=window["handle"])

    kwargs: Dict[str, Any] = {}
    if auto_id:
        kwargs["auto_id"] = auto_id
    if control_type:
        kwargs["control_type"] = control_type
    if name:
        # pywinauto UIA backend uses "title" not "name" for child_window filters
        kwargs["title"] = name
    if class_name:
        kwargs["class_name"] = class_name

    try:
        if regex_name and name:
            # pywinauto >= 0.6.5 supports name_re.
            element = dlg.child_window(title_re=name, **{
                k: v for k, v in kwargs.items() if k not in ("title",)
            })
        else:
            element = dlg.child_window(**kwargs)
        rect = element.rectangle()
        _auto_id_attr = getattr(element.element_info, "automation_id", None)
        auto_id_val = _auto_id_attr() if callable(_auto_id_attr) else (_auto_id_attr if _auto_id_attr is not None else "")
        desc = {
            "found": True,
            "auto_id": auto_id_val,
            "control_type": str(element.element_info.control_type),
            "name": element.window_text(),
            "class_name": element.friendly_class_name(),
            "rect": {
                "left": int(rect.left),
                "top": int(rect.top),
                "right": int(rect.right),
                "bottom": int(rect.bottom),
                "width": int(rect.width()),
                "height": int(rect.height()),
            },
            "handle": int(element.handle) if hasattr(element, "handle") else 0,
            "window_handle": window["handle"],
            "window_title": window["title"],
        }
        return desc
    except ElementNotFoundError:
        return None
    except Exception as exc:
        return {"found": False, "error": str(exc)}


def click_element(
    title: Optional[str] = None,
    handle: Optional[int] = None,
    pid: Optional[int] = None,
    *,
    button: str = "left",
    double: bool = False,
    **find_kwargs: Any,
) -> Dict[str, Any]:
    """Find an element then invoke its click (or double-click)."""
    safety.check_emergency_stop()
    desc = find_element(title=title, handle=handle, pid=pid, **find_kwargs)
    if not desc or not desc.get("found"):
        return {"ok": False, "error": "element not found", "criteria": find_kwargs}
    window = window_mgmt.find_window(title=title, handle=handle, pid=pid)
    app = _resolve_app(window)
    dlg = app.window(handle=window["handle"])
    kwargs = {k: v for k, v in find_kwargs.items() if k in {"auto_id", "control_type", "name", "class_name"}}
    # pywinauto UIA backend expects "title" not "name"
    if "name" in kwargs:
        kwargs["title"] = kwargs.pop("name")
    if find_kwargs.get("regex_name") and find_kwargs.get("name"):
        kwargs.pop("title", None)
        element = dlg.child_window(title_re=find_kwargs["name"], **{k: v for k, v in kwargs.items()})
    else:
        element = dlg.child_window(**kwargs)
    if double:
        try:
            element.double_click(button=button)
        except TypeError:
            element.double_click()
    else:
        try:
            element.click(button=button)
        except TypeError:
            element.click()
    return {"ok": True, "element": desc}


def set_text(
    title: Optional[str] = None,
    handle: Optional[int] = None,
    pid: Optional[int] = None,
    *,
    value: str,
    **find_kwargs: Any,
) -> Dict[str, Any]:
    """Set the text content of an Edit / Document control."""
    safety.check_emergency_stop()
    window = window_mgmt.find_window(title=title, handle=handle, pid=pid)
    if window is None:
        return {"ok": False, "error": "window not found"}
    app = _resolve_app(window)
    dlg = app.window(handle=window["handle"])
    kwargs = {k: v for k, v in find_kwargs.items() if k in {"auto_id", "control_type", "name", "class_name"}}
    # pywinauto UIA backend expects "title" not "name"
    if "name" in kwargs:
        kwargs["title"] = kwargs.pop("name")
    try:
        element = dlg.child_window(**kwargs)
    except Exception as exc:
        return {"ok": False, "error": f"element not found: {exc}"}
    try:
        element.set_edit_text(value)  # type: ignore[attr-defined]
    except Exception:
        try:
            element.set_text(value)  # type: ignore[attr-defined]
        except Exception as exc:
            return {"ok": False, "error": f"set_text failed: {exc}"}
    return {"ok": True, "value": value}


def element_text(
    title: Optional[str] = None,
    handle: Optional[int] = None,
    pid: Optional[int] = None,
    **find_kwargs: Any,
) -> Optional[str]:
    desc = find_element(title=title, handle=handle, pid=pid, **find_kwargs)
    if not desc or not desc.get("found"):
        return None
    # Try to get the actual element text (for Edit controls, get the edit text)
    window = window_mgmt.find_window(title=title, handle=handle, pid=pid)
    if window is None:
        return desc.get("name")
    try:
        app = _resolve_app(window)
        dlg = app.window(handle=window["handle"])
        kwargs = {k: v for k, v in find_kwargs.items() if k in {"auto_id", "control_type", "name", "class_name"}}
        if "name" in kwargs:
            kwargs["title"] = kwargs.pop("name")
        el = dlg.child_window(**kwargs)
        # For Edit controls, get_value() returns the actual editable text
        try:
            val = el.get_value()
            if val is not None and val != "":
                return str(val)
        except Exception:
            pass
        try:
            text_val = el.texts()
            if text_val:
                return "\n".join(text_val)
        except Exception:
            pass
        # For Edit controls, get_value() returns the actual editable text
        try:
            val = el.get_value()
            if val is not None and val != "":
                return str(val)
        except Exception:
            pass
        try:
            text_val = el.window_text()
            if text_val:
                return text_val
        except Exception:
            pass
    except Exception:
        pass
    return desc.get("name")


def wait_element(
    title: Optional[str] = None,
    handle: Optional[int] = None,
    pid: Optional[int] = None,
    *,
    timeout: float = 10.0,
    interval: float = 0.5,
    **find_kwargs: Any,
) -> Optional[Dict[str, Any]]:
    """Poll :func:`find_element` until it returns a result or the timeout elapses."""
    deadline = time.time() + max(0.1, float(timeout))
    while time.time() < deadline:
        safety.check_emergency_stop()
        desc = find_element(title=title, handle=handle, pid=pid, **find_kwargs)
        if desc and desc.get("found"):
            return desc
        time.sleep(max(0.05, float(interval)))
    return None