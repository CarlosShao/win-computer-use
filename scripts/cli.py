"""workbuddy-computer-use CLI entry point.

This is the single binary the SKILL.md tells WorkBuddy to call via
``python scripts/cli.py <command> [args...]``.  Every subcommand emits
a single JSON object to stdout and exits with code 0 on success / 1 on
failure.  Errors are also emitted as JSON so the calling LLM can
``json.loads`` the result without bespoke parsing.

Design goals:

* Zero configuration -- sensible defaults that "just work" on a fresh
  Windows install with the requirements.txt installed.
* Stateless, side-effect-free, re-entrant -- safe to call from
  multiple processes at once.  Only :mod:`safety` carries cross-call
  state (FAILSAFE + emergency-stop flag).
* Discoverable -- ``python cli.py --help`` lists every command.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# Make sibling modules importable when invoked as a script.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import image_match  # noqa: E402
import input_control  # noqa: E402
import ocr  # noqa: E402
import safety  # noqa: E402
import screen  # noqa: E402
import ui_find  # noqa: E402
import window_mgmt  # noqa: E402


def _ok(action: str, data: Any = None) -> int:
    print(json.dumps({"ok": True, "action": action, "data": data}, ensure_ascii=False))
    return 0


def _err(action: str, error: str, extra: Optional[Dict[str, Any]] = None) -> int:
    payload: Dict[str, Any] = {"ok": False, "action": action, "error": error}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))
    return 1


def _wrap(action: str, fn: Callable[[], Any]) -> int:
    try:
        result = fn()
        return _ok(action, result)
    except safety.EmergencyStop as exc:
        return _err(action, f"emergency_stop: {exc}")
    except SystemExit as exc:  # argparse --help raises SystemExit(0)
        raise
    except Exception as exc:
        tb = traceback.format_exc()
        return _err(action, f"{type(exc).__name__}: {exc}", {"traceback": tb})


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


def cmd_screenshot(args: argparse.Namespace) -> int:
    def _run():
        region = None
        if args.region:
            r = [int(v) for v in args.region.split(",")]
            if len(r) != 4:
                raise ValueError("--region expects 'left,top,width,height'")
            region = tuple(r)  # type: ignore[assignment]
        info = screen.screenshot(
            region=region,
            output_path=args.output,
            return_base64=args.base64,
            monitor_index=args.monitor,
        )
        if not args.base64:
            info.pop("base64", None)
        return info

    return _wrap("screenshot", _run)


def cmd_screen_size(args: argparse.Namespace) -> int:
    return _wrap("screen_size", lambda: screen.screen_size())


def cmd_pixel(args: argparse.Namespace) -> int:
    return _wrap("pixel", lambda: screen.pixel_color(args.x, args.y))


# --- mouse -----------------------------------------------------------------


def cmd_mouse_position(args: argparse.Namespace) -> int:
    return _wrap("mouse_position", input_control.mouse_position)


def cmd_move(args: argparse.Namespace) -> int:
    return _wrap("move", lambda: input_control.move_to(args.x, args.y, args.duration))


def cmd_click(args: argparse.Namespace) -> int:
    return _wrap("click", lambda: input_control.click(args.x, args.y, args.button, args.clicks, args.interval))


def cmd_double_click(args: argparse.Namespace) -> int:
    return _wrap("double_click", lambda: input_control.double_click(args.x, args.y))


def cmd_right_click(args: argparse.Namespace) -> int:
    return _wrap("right_click", lambda: input_control.right_click(args.x, args.y))


def cmd_drag(args: argparse.Namespace) -> int:
    def _run():
        return input_control.drag(args.x1, args.y1, args.x2, args.y2, args.duration, args.button)
    return _wrap("drag", _run)


def cmd_scroll(args: argparse.Namespace) -> int:
    return _wrap("scroll", lambda: input_control.scroll(args.clicks, args.x, args.y))


# --- keyboard --------------------------------------------------------------


def cmd_type(args: argparse.Namespace) -> int:
    return _wrap("type", lambda: input_control.type_text(args.text, args.interval))


def cmd_hotkey(args: argparse.Namespace) -> int:
    return _wrap("hotkey", lambda: input_control.hotkey(*args.keys))


def cmd_key_press(args: argparse.Namespace) -> int:
    return _wrap("key_press", lambda: input_control.key_press(args.key))


def cmd_key_down(args: argparse.Namespace) -> int:
    return _wrap("key_down", lambda: input_control.key_down(args.key))


def cmd_key_up(args: argparse.Namespace) -> int:
    return _wrap("key_up", lambda: input_control.key_up(args.key))


def cmd_wait(args: argparse.Namespace) -> int:
    return _wrap("wait", lambda: input_control.wait(args.seconds))


# --- windows ---------------------------------------------------------------


def _window_arg(args: argparse.Namespace) -> Dict[str, Any]:
    """Pull ``title/handle/pid`` out of argparse namespace."""
    handle = args.handle if hasattr(args, "handle") else None
    pid = args.pid if hasattr(args, "pid") else None
    title = args.title if hasattr(args, "title") else None
    return {"title": title, "handle": handle, "pid": pid}


def cmd_list_windows(args: argparse.Namespace) -> int:
    def _run():
        return window_mgmt.list_windows(
            title_filter=args.filter,
            visible_only=not args.all_,
            regex=args.regex,
        )
    return _wrap("list_windows", _run)


def cmd_find_window(args: argparse.Namespace) -> int:
    return _wrap("find_window", lambda: window_mgmt.find_window(**_window_arg(args)))


def cmd_activate(args: argparse.Namespace) -> int:
    return _wrap("activate_window", lambda: window_mgmt.activate_window(**_window_arg(args)))


def cmd_minimize(args: argparse.Namespace) -> int:
    return _wrap("minimize_window", lambda: window_mgmt.minimize_window(**_window_arg(args)))


def cmd_maximize(args: argparse.Namespace) -> int:
    return _wrap("maximize_window", lambda: window_mgmt.maximize_window(**_window_arg(args)))


def cmd_restore(args: argparse.Namespace) -> int:
    return _wrap("restore_window", lambda: window_mgmt.restore_window(**_window_arg(args)))


def cmd_close(args: argparse.Namespace) -> int:
    return _wrap("close_window", lambda: window_mgmt.close_window(**_window_arg(args)))


def cmd_window_rect(args: argparse.Namespace) -> int:
    return _wrap("window_rect", lambda: window_mgmt.window_rect(**_window_arg(args)))


# --- ui automation ---------------------------------------------------------


def _ui_kwargs(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "auto_id": args.auto_id,
        "control_type": args.control_type,
        "name": args.name,
        "class_name": args.class_name,
        "regex_name": args.regex_name,
    }


def cmd_find_element(args: argparse.Namespace) -> int:
    def _run():
        return ui_find.find_element(**_window_arg(args), **_ui_kwargs(args))
    return _wrap("find_element", _run)


def cmd_click_element(args: argparse.Namespace) -> int:
    def _run():
        return ui_find.click_element(
            **_window_arg(args),
            button=args.button,
            double=args.double,
            **_ui_kwargs(args),
        )
    return _wrap("click_element", _run)


def cmd_set_text(args: argparse.Namespace) -> int:
    def _run():
        return ui_find.set_text(**_window_arg(args), value=args.value, **_ui_kwargs(args))
    return _wrap("set_text", _run)


def cmd_element_text(args: argparse.Namespace) -> int:
    return _wrap("element_text", lambda: ui_find.element_text(**_window_arg(args), **_ui_kwargs(args)))


def cmd_wait_element(args: argparse.Namespace) -> int:
    def _run():
        return ui_find.wait_element(
            **_window_arg(args),
            timeout=args.timeout,
            interval=args.interval,
            **_ui_kwargs(args),
        )
    return _wrap("wait_element", _run)


# --- image match -----------------------------------------------------------


def _region_tuple(s: Optional[str]):
    if not s:
        return None
    parts = [int(v) for v in s.split(",")]
    if len(parts) != 4:
        raise ValueError("--region expects 'left,top,width,height'")
    return tuple(parts)  # type: ignore[return-value]


def cmd_find_image(args: argparse.Namespace) -> int:
    return _wrap(
        "find_image",
        lambda: image_match.find_image(
            args.template,
            region=_region_tuple(args.region),
            threshold=args.threshold,
            max_results=args.max_results,
            multi_scale=args.multi_scale,
        ),
    )


def cmd_click_image(args: argparse.Namespace) -> int:
    return _wrap(
        "click_image",
        lambda: image_match.click_image(
            args.template,
            region=_region_tuple(args.region),
            threshold=args.threshold,
            button=args.button,
            multi_scale=args.multi_scale,
        ),
    )


def cmd_wait_image(args: argparse.Namespace) -> int:
    return _wrap(
        "wait_image",
        lambda: image_match.wait_for_image(
            args.template,
            region=_region_tuple(args.region),
            timeout=args.timeout,
            interval=args.interval,
            threshold=args.threshold,
            multi_scale=args.multi_scale,
        ),
    )


def cmd_count_image(args: argparse.Namespace) -> int:
    return _wrap(
        "count_image",
        lambda: image_match.count_image(
            args.template,
            region=_region_tuple(args.region),
            threshold=args.threshold,
            multi_scale=args.multi_scale,
        ),
    )


# --- ocr -------------------------------------------------------------------

def cmd_smart_click(args: argparse.Namespace) -> int:
    """Smart click with auto fallback: UI Automation → OCR → Image."""
    def _run():
        text = args.text
        auto_id = args.auto_id
        control_type = args.control_type
        name = args.name
        class_name = args.class_name
        template = args.template
        region = _region_tuple(args.region)
        button = args.button
        timeout = args.timeout
        multi_scale = args.multi_scale

        # Try UI Automation first
        if auto_id or control_type or name or class_name:
            try:
                result = ui_find.click_element(
                    auto_id=auto_id,
                    control_type=control_type,
                    name=name,
                    class_name=class_name,
                    button=button,
                    double=False,
                )
                if result and result.get("ok"):
                    result["method"] = "ui_automation"
                    return result
            except Exception:
                pass

        # Try OCR (find text, then click centre)
        if text:
            try:
                words = ocr.ocr_words(region=region, lang="chi_sim+eng")
                if words:
                    best = None
                    for w in words:
                        if text in w.get("text", ""):
                            if best is None or w.get("conf", 0) > best.get("conf", 0):
                                best = w
                    if best:
                        cx = best["x"] + best["w"] // 2
                        cy = best["y"] + best["h"] // 2
                        input_control.click(cx, cy, button=button)
                        return {
                            "ok": True,
                            "method": "ocr",
                            "text": best["text"],
                            "clicked": {"x": cx, "y": cy, "button": button},
                        }
            except Exception:
                pass

        # Fallback to image matching
        if template:
            result = image_match.click_image(
                template,
                region=region,
                threshold=0.82,
                button=button,
                multi_scale=multi_scale,
            )
            if result and result.get("ok"):
                result["method"] = "image_match"
                return result

        raise RuntimeError("smart_click: all methods failed (UI Automation / OCR / Image)")

    return _wrap("smart_click", _run)


# --- ocr -------------------------------------------------------------------


def cmd_ocr(args: argparse.Namespace) -> int:
    return _wrap(
        "ocr",
        lambda: ocr.ocr_text(
            region=_region_tuple(args.region),
            lang=args.lang,
            tesseract_cmd=args.tesseract,
            backend=args.backend,
        ),
    )


def cmd_ocr_words(args: argparse.Namespace) -> int:
    return _wrap(
        "ocr_words",
        lambda: ocr.ocr_words(
            region=_region_tuple(args.region),
            lang=args.lang,
            tesseract_cmd=args.tesseract,
            backend=args.backend,
        ),
    )


# --- safety ----------------------------------------------------------------


def cmd_emergency_stop(args: argparse.Namespace) -> int:
    safety.emergency_stop()
    return _ok("emergency_stop", {"stopped": True})


def cmd_clear_stop(args: argparse.Namespace) -> int:
    safety.clear_stop()
    return _ok("clear_stop", {"stopped": False})


def cmd_failsafe(args: argparse.Namespace) -> int:
    safety.set_failsafe(args.enable == "on")
    return _ok("failsafe", {"enabled": safety.failsafe_enabled()})


def cmd_stop_status(args: argparse.Namespace) -> int:
    return _ok("stop_status", {"stopped": safety.is_stopped(), "failsafe": safety.failsafe_enabled()})


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="computer-use",
        description="Windows desktop automation CLI (screenshot / mouse / keyboard / windows / UI / image / OCR).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # screen
    sp = sub.add_parser("screenshot", help="Capture a screenshot.")
    sp.add_argument("--region", default=None, help="left,top,width,height")
    sp.add_argument("--output", default=None, help="Where to save the PNG.")
    sp.add_argument("--base64", action="store_true", help="Include base64 PNG in JSON output.")
    sp.add_argument("--monitor", type=int, default=0, help="Monitor index (default 0).")
    sp.set_defaults(func=cmd_screenshot)

    sub.add_parser("screen-size").set_defaults(func=cmd_screen_size)
    pp = sub.add_parser("pixel", help="Read a pixel colour.")
    pp.add_argument("x", type=int)
    pp.add_argument("y", type=int)
    pp.set_defaults(func=cmd_pixel)

    # mouse
    mp = sub.add_parser("mouse-position").set_defaults(func=cmd_mouse_position)
    mpv = sub.add_parser("move", help="Move the cursor.")
    mpv.add_argument("x", type=int)
    mpv.add_argument("y", type=int)
    mpv.add_argument("--duration", type=float, default=0.0)
    mpv.set_defaults(func=cmd_move)

    cc = sub.add_parser("click", help="Click at the given coordinates.")
    cc.add_argument("x", type=int)
    cc.add_argument("y", type=int)
    cc.add_argument("--button", choices=["left", "right", "middle"], default="left")
    cc.add_argument("--clicks", type=int, default=1)
    cc.add_argument("--interval", type=float, default=0.05)
    cc.set_defaults(func=cmd_click)

    dc = sub.add_parser("double-click")
    dc.add_argument("x", type=int)
    dc.add_argument("y", type=int)
    dc.set_defaults(func=cmd_double_click)

    rc = sub.add_parser("right-click")
    rc.add_argument("x", type=int)
    rc.add_argument("y", type=int)
    rc.set_defaults(func=cmd_right_click)

    dr = sub.add_parser("drag", help="Drag from A to B.")
    dr.add_argument("x1", type=int)
    dr.add_argument("y1", type=int)
    dr.add_argument("x2", type=int)
    dr.add_argument("y2", type=int)
    dr.add_argument("--duration", type=float, default=0.3)
    dr.add_argument("--button", choices=["left", "right", "middle"], default="left")
    dr.set_defaults(func=cmd_drag)

    sc = sub.add_parser("scroll", help="Scroll the mouse wheel.")
    sc.add_argument("clicks", type=int, help="Positive = up, negative = down.")
    sc.add_argument("--x", type=int, default=None)
    sc.add_argument("--y", type=int, default=None)
    sc.set_defaults(func=cmd_scroll)

    # keyboard
    kt = sub.add_parser("type", help="Type literal text.")
    kt.add_argument("text")
    kt.add_argument("--interval", type=float, default=0.02)
    kt.set_defaults(func=cmd_type)

    hk = sub.add_parser("hotkey", help="Press a key chord (e.g. ctrl c).")
    hk.add_argument("keys", nargs="+")
    hk.set_defaults(func=cmd_hotkey)

    kp = sub.add_parser("key-press")
    kp.add_argument("key")
    kp.set_defaults(func=cmd_key_press)

    kd = sub.add_parser("key-down")
    kd.add_argument("key")
    kd.set_defaults(func=cmd_key_down)

    ku = sub.add_parser("key-up")
    ku.add_argument("key")
    ku.set_defaults(func=cmd_key_up)

    wt = sub.add_parser("wait")
    wt.add_argument("seconds", type=float)
    wt.set_defaults(func=cmd_wait)

    # windows
    def _win_args(parser: argparse.ArgumentParser, required: bool = False) -> None:
        parser.add_argument("--title", default=None)
        parser.add_argument("--handle", type=int, default=None)
        parser.add_argument("--pid", type=int, default=None)
        if required:
            grp = parser.add_mutually_exclusive_group(required=True)
            grp.add_argument("--title", dest="title", default=None)
            grp.add_argument("--handle", dest="handle", type=int, default=None)
            grp.add_argument("--pid", dest="pid", type=int, default=None)

    lw = sub.add_parser("list-windows")
    lw.add_argument("--filter", default=None, help="Substring or regex to filter by title.")
    lw.add_argument("--regex", action="store_true", help="Treat --filter as regex.")
    lw.add_argument("--all", dest="all_", action="store_true", help="Include hidden windows.")
    lw.set_defaults(func=cmd_list_windows)

    fw = sub.add_parser("find-window")
    _win_args(fw)
    fw.set_defaults(func=cmd_find_window)

    for name, fn in [
        ("activate-window", cmd_activate),
        ("minimize", cmd_minimize),
        ("maximize", cmd_maximize),
        ("restore", cmd_restore),
        ("close-window", cmd_close),
        ("window-rect", cmd_window_rect),
    ]:
        sp = sub.add_parser(name)
        _win_args(sp)
        sp.set_defaults(func=fn)

    # ui find
    def _ui_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--auto-id", default=None)
        parser.add_argument("--control-type", default=None)
        parser.add_argument("--name", default=None)
        parser.add_argument("--class-name", default=None)
        parser.add_argument("--regex-name", action="store_true")

    fe = sub.add_parser("find-element")
    _win_args(fe)
    _ui_args(fe)
    fe.set_defaults(func=cmd_find_element)

    ce = sub.add_parser("click-element")
    _win_args(ce)
    _ui_args(ce)
    ce.add_argument("--button", choices=["left", "right", "middle"], default="left")
    ce.add_argument("--double", action="store_true")
    ce.set_defaults(func=cmd_click_element)

    st = sub.add_parser("set-text")
    _win_args(st)
    _ui_args(st)
    st.add_argument("--value", required=True)
    st.set_defaults(func=cmd_set_text)

    et = sub.add_parser("element-text")
    _win_args(et)
    _ui_args(et)
    et.set_defaults(func=cmd_element_text)

    we = sub.add_parser("wait-element")
    _win_args(we)
    _ui_args(we)
    we.add_argument("--timeout", type=float, default=10.0)
    we.add_argument("--interval", type=float, default=0.5)
    we.set_defaults(func=cmd_wait_element)

    # image match
    def _img_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("template", help="Path to template PNG.")
        parser.add_argument("--region", default=None)
        parser.add_argument("--threshold", type=float, default=0.82)

    fi = sub.add_parser("find-image")
    _img_args(fi)
    fi.add_argument("--max-results", type=int, default=1)
    fi.add_argument("--multi-scale", action="store_true", help="Multi-scale matching for DPI scaling.")
    fi.set_defaults(func=cmd_find_image)

    ci = sub.add_parser("click-image")
    _img_args(ci)
    ci.add_argument("--button", choices=["left", "right", "middle"], default="left")
    ci.add_argument("--multi-scale", action="store_true", help="Multi-scale matching for DPI scaling.")
    ci.set_defaults(func=cmd_click_image)

    wi = sub.add_parser("wait-image")
    _img_args(wi)
    wi.add_argument("--timeout", type=float, default=10.0)
    wi.add_argument("--interval", type=float, default=0.5)
    wi.add_argument("--multi-scale", action="store_true", help="Multi-scale matching for DPI scaling.")
    wi.set_defaults(func=cmd_wait_image)

    coi = sub.add_parser("count-image")
    _img_args(coi)
    coi.add_argument("--multi-scale", action="store_true", help="Multi-scale matching for DPI scaling.")
    coi.set_defaults(func=cmd_count_image)

    # ocr
    oc = sub.add_parser("ocr")
    oc.add_argument("--region", default=None)
    oc.add_argument("--lang", default="chi_sim+eng")
    oc.add_argument("--tesseract", default=None)
    oc.add_argument("--backend", default="auto", choices=["auto", "rapidocr", "tesseract", "tesserocr"],
                    help="OCR backend: auto (try rapidocr first), rapidocr, tesseract, tesserocr")
    oc.set_defaults(func=cmd_ocr)

    ow = sub.add_parser("ocr-words")
    ow.add_argument("--region", default=None)
    ow.add_argument("--lang", default="chi_sim+eng")
    ow.add_argument("--tesseract", default=None)
    ow.add_argument("--backend", default="auto", choices=["auto", "rapidocr", "tesseract", "tesserocr"],
                    help="OCR backend: auto (try rapidocr first), rapidocr, tesseract, tesserocr")
    ow.set_defaults(func=cmd_ocr_words)

    # --- smart click (auto fallback) ---------------------------------
    sc = sub.add_parser("smart-click", help="Click by text/element/image with auto fallback.")
    sc.add_argument("--text", default=None, help="Text to find via UI Automation or OCR.")
    sc.add_argument("--auto-id", default=None, help="UI Automation auto-id.")
    sc.add_argument("--control-type", default=None)
    sc.add_argument("--name", default=None)
    sc.add_argument("--class-name", default=None)
    sc.add_argument("--template", default=None, help="Template PNG for image matching fallback.")
    sc.add_argument("--region", default=None)
    sc.add_argument("--button", choices=["left", "right", "middle"], default="left")
    sc.add_argument("--timeout", type=float, default=5.0)
    sc.add_argument("--multi-scale", action="store_true")
    sc.set_defaults(func=cmd_smart_click)

    # safety
    sub.add_parser("emergency-stop").set_defaults(func=cmd_emergency_stop)
    sub.add_parser("clear-stop").set_defaults(func=cmd_clear_stop)
    fs = sub.add_parser("failsafe")
    fs.add_argument("enable", choices=["on", "off"])
    fs.set_defaults(func=cmd_failsafe)
    sub.add_parser("stop-status").set_defaults(func=cmd_stop_status)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())