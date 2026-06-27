"""win-computer-use MCP-compatible HTTP server.

This server wraps all ``cli.py`` subcommands as HTTP endpoints,
so AI agents can call them without cold-starting a Python process
for every action.

Run::

    python server.py              # default :8000
    python server.py --port 9000

Endpoints
-----------
* ``POST /screenshot``       → ``{"ok": true, "data": {...}}``
* ``POST /mouse/position`` → ``{"ok": true, "data": {"x":..,"y":..}}``
* ``POST /click``            → ``{"ok": true, "data": {...}}``
* … (one endpoint per ``cli.py`` subcommand)

The server is stateless except for :mod:`safety` (emergency-stop
flag is shared across requests).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn

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

# ---------------------------------------------------------------------------
# Helpers – same as cli.py but return dicts instead of printing JSON
# ---------------------------------------------------------------------------


def _ok(data: Any = None) -> JSONResponse:
    return JSONResponse(content={"ok": True, "data": data}, status_code=200)


def _err(error: str, extra: Optional[Dict[str, Any]] = None) -> JSONResponse:
    payload: Dict[str, Any] = {"ok": False, "error": error}
    if extra:
        payload.update(extra)
    return JSONResponse(content=payload, status_code=200)


def _wrap(fn: Callable[[], Any]) -> JSONResponse:
    try:
        result = fn()
        return _ok(result)
    except safety.EmergencyStop as exc:
        return _err(f"emergency_stop: {exc}")
    except Exception as exc:
        tb = traceback.format_exc()
        return _err(f"{type(exc).__name__}: {exc}", {"traceback": tb})


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="win-computer-use Server",
    description="Windows desktop automation HTTP API (wraps cli.py subcommands)",
    version="1.0.0",
)


# --- screen -----------------------------------------------------------------

@app.post("/screenshot")
def screenshot(
    region: Optional[str] = None,
    output: Optional[str] = None,
    base64: bool = False,
    monitor: int = 0,
):
    def _run():
        r = None
        if region:
            parts = [int(v) for v in region.split(",")]
            if len(parts) != 4:
                raise ValueError("--region expects 'left,top,width,height'")
            r = tuple(parts)
        info = screen.screenshot(region=r, output_path=output, return_base64=base64, monitor_index=monitor)
        if not base64:
            info.pop("base64", None)
        return info
    return _wrap(_run)


@app.get("/screen-size")
def screen_size():
    return _wrap(lambda: screen.screen_size())


@app.get("/pixel/{x}/{y}")
def pixel(x: int, y: int):
    return _wrap(lambda: screen.pixel_color(x, y))


# --- mouse ------------------------------------------------------------------

@app.get("/mouse/position")
def mouse_position():
    return _wrap(input_control.mouse_position)


@app.post("/mouse/move/{x}/{y}")
def mouse_move(x: int, y: int, duration: float = 0.0):
    return _wrap(lambda: input_control.move_to(x, y, duration))


@app.post("/click/{x}/{y}")
def click(x: int, y: int, button: str = "left", clicks: int = 1, interval: float = 0.05):
    return _wrap(lambda: input_control.click(x, y, button, clicks, interval))


@app.post("/double-click/{x}/{y}")
def double_click(x: int, y: int):
    return _wrap(lambda: input_control.double_click(x, y))


@app.post("/right-click/{x}/{y}")
def right_click(x: int, y: int):
    return _wrap(lambda: input_control.right_click(x, y))


@app.post("/drag")
def drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.3, button: str = "left"):
    return _wrap(lambda: input_control.drag(x1, y1, x2, y2, duration, button))


@app.post("/scroll")
def scroll(clicks: int, x: Optional[int] = None, y: Optional[int] = None):
    return _wrap(lambda: input_control.scroll(clicks, x, y))


# --- keyboard ---------------------------------------------------------------

@app.post("/type")
def type_text(text: str, interval: float = 0.02):
    return _wrap(lambda: input_control.type_text(text, interval))


@app.post("/hotkey")
def hotkey(keys: str):  # comma-separated, e.g. "ctrl,c"
    ks = [k.strip() for k in keys.split(",")]
    return _wrap(lambda: input_control.hotkey(*ks))


@app.post("/key-press/{key}")
def key_press(key: str):
    return _wrap(lambda: input_control.key_press(key))


@app.post("/key-down/{key}")
def key_down(key: str):
    return _wrap(lambda: input_control.key_down(key))


@app.post("/key-up/{key}")
def key_up(key: str):
    return _wrap(lambda: input_control.key_up(key))


# --- windows -----------------------------------------------------------------

@app.get("/windows")
def list_windows(filter: Optional[str] = None, regex: bool = False, all: bool = False):
    return _wrap(lambda: window_mgmt.list_windows(
        title_filter=filter,
        visible_only=not all,
        regex=regex,
    ))


@app.post("/window/activate")
def activate_window(title: Optional[str] = None, handle: Optional[int] = None, pid: Optional[int] = None):
    return _wrap(lambda: window_mgmt.activate_window(title=title, handle=handle, pid=pid))


@app.post("/window/close")
def close_window(title: Optional[str] = None, handle: Optional[int] = None, pid: Optional[int] = None):
    return _wrap(lambda: window_mgmt.close_window(title=title, handle=handle, pid=pid))


# --- ui automation ----------------------------------------------------------

@app.post("/ui/find")
def find_element(
    title: Optional[str] = None,
    handle: Optional[int] = None,
    pid: Optional[int] = None,
    auto_id: Optional[str] = None,
    control_type: Optional[str] = None,
    name: Optional[str] = None,
    class_name: Optional[str] = None,
    regex_name: bool = False,
):
    return _wrap(lambda: ui_find.find_element(
        title=title, handle=handle, pid=pid,
        auto_id=auto_id, control_type=control_type,
        name=name, class_name=class_name,
        regex_name=regex_name,
    ))


@app.post("/ui/click")
def click_element(
    title: Optional[str] = None,
    handle: Optional[int] = None,
    pid: Optional[int] = None,
    auto_id: Optional[str] = None,
    control_type: Optional[str] = None,
    name: Optional[str] = None,
    class_name: Optional[str] = None,
    regex_name: bool = False,
    button: str = "left",
    double: bool = False,
):
    return _wrap(lambda: ui_find.click_element(
        title=title, handle=handle, pid=pid,
        auto_id=auto_id, control_type=control_type,
        name=name, class_name=class_name,
        regex_name=regex_name,
        button=button, double=double,
    ))


# --- image match ------------------------------------------------------------

@app.post("/image/find")
def find_image(template: str, region: Optional[str] = None, threshold: float = 0.82, max_results: int = 1, multi_scale: bool = False):
    def _run():
        r = None
        if region:
            parts = [int(v) for v in region.split(",")]
            if len(parts) != 4:
                raise ValueError("region expects 'left,top,width,height'")
            r = tuple(parts)
        return image_match.find_image(template, region=r, threshold=threshold, max_results=max_results, multi_scale=multi_scale)
    return _wrap(_run)


@app.post("/image/click")
def click_image(template: str, region: Optional[str] = None, threshold: float = 0.82, button: str = "left", multi_scale: bool = False):
    def _run():
        r = None
        if region:
            parts = [int(v) for v in region.split(",")]
            if len(parts) != 4:
                raise ValueError("region expects 'left,top,width,height'")
            r = tuple(parts)
        return image_match.click_image(template, region=r, threshold=threshold, button=button, multi_scale=multi_scale)
    return _wrap(_run)


# --- ocr --------------------------------------------------------------------

@app.post("/ocr")
def ocr_text(region: Optional[str] = None, lang: str = "chi_sim+eng", backend: str = "auto"):
    def _run():
        r = None
        if region:
            parts = [int(v) for v in region.split(",")]
            if len(parts) != 4:
                raise ValueError("region expects 'left,top,width,height'")
            r = tuple(parts)
        return ocr.ocr_text(region=r, lang=lang, backend=backend)
    return _wrap(_run)


# --- safety ------------------------------------------------------------------

@app.post("/safety/emergency-stop")
def emergency_stop():
    safety.emergency_stop()
    return _ok({"stopped": True})


@app.get("/safety/stop-status")
def stop_status():
    return _ok({"stopped": safety.is_stopped(), "failsafe": safety.failsafe_enabled()})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(description="win-computer-use HTTP server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default 8000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default 127.0.0.1)")
    args = parser.parse_args(argv)

    print(f"[win-computer-use] Starting server on {args.host}:{args.port} ...", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
