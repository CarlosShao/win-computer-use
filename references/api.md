# workbuddy-computer-use — API Reference

This document lists every CLI subcommand exposed by `scripts/cli.py`.
Each section lists the command name, all arguments, the JSON schema it
returns, and a small example.

> All commands emit a single JSON object on stdout.  Success returns
> `{"ok": true, "action": ..., "data": ...}` with exit code `0`.
> Errors return `{"ok": false, "action": ..., "error": "...", "traceback": "..."}`
> with exit code `1`.

Common conventions:

* `--region` accepts `left,top,width,height` in absolute screen pixels.
* `--threshold` defaults to `0.82` for image matching (env var
  `COMPUTER_USE_MATCH_THRESHOLD` overrides).
* All coordinates are **absolute physical pixels** after DPI
  awareness has been enabled.  This is handled automatically by
  `platform.enable_dpi_awareness()` on import.

---

## Screen

### `screenshot`

| Arg | Type | Description |
|---|---|---|
| `--region` | string | `left,top,width,height` to crop. |
| `--output` | string | Override output path. |
| `--base64` | flag | Embed PNG as base64 in the JSON. |
| `--monitor` | int | Monitor index (default `0`). |

```json
{"ok": true, "action": "screenshot", "data": {
    "path": ".../screenshots/shot-20260626-153012-833.png",
    "width": 1920, "height": 1080, "bytes": 248731
}}
```

### `screen-size`

```json
{"ok": true, "data": {"width": 1920, "height": 1080}}
```

### `pixel <x> <y>`

```json
{"ok": true, "data": {"r": 240, "g": 240, "b": 240}}
```

---

## Mouse

| Command | Args |
|---|---|
| `mouse-position` | — |
| `move <x> <y>` | `--duration` |
| `click <x> <y>` | `--button left\|right\|middle`, `--clicks`, `--interval` |
| `double-click <x> <y>` | — |
| `right-click <x> <y>` | — |
| `drag <x1> <y1> <x2> <y2>` | `--duration`, `--button` |
| `scroll <clicks>` | `--x`, `--y` |

`<clicks>` is signed: positive = scroll up / away from user; negative
= scroll down.

---

## Keyboard

| Command | Args |
|---|---|
| `type <text>` | `--interval` |
| `hotkey <k1> [k2 ...]` | multiple keys (order matters for modifiers) |
| `key-press <key>` | single key |
| `key-down <key>` | hold a key |
| `key-up <key>` | release a key |
| `wait <seconds>` | sleep, polling emergency stop |

Recognised key names follow `pyautogui.KEYBOARD_KEYS`:

* Letters / digits: `a`–`z`, `0`–`9`
* Whitespace: `space`, `enter`, `tab`, `escape`
* Arrows: `up`, `down`, `left`, `right`
* Function keys: `f1`–`f24`
* Modifiers: `ctrl`, `alt`, `shift`, `win`, `command`
* Editing: `backspace`, `delete`, `home`, `end`, `pageup`, `pagedown`,
  `insert`, `capslock`, `numlock`
* Special: `printscreen`, `scrolllock`, `pause`

For non-ASCII text, `type` automatically falls back to clipboard
paste via `pyperclip`.

---

## Windows

All `*window*` commands accept `--title`, `--handle`, and `--pid`.
At least one is required for `find-window` and the action commands.

### `list-windows`

| Arg | Description |
|---|---|
| `--filter` | substring (or regex when `--regex` is set) |
| `--regex` | treat `--filter` as regex |
| `--all` | include hidden windows |

```json
{"ok": true, "data": [
    {"title": "Untitled - Notepad", "handle": 123456, "pid": 7890,
     "visible": true,
     "rect": {"left": 100, "top": 100, "right": 800, "bottom": 600,
              "width": 700, "height": 500}}
]}
```

### `find-window`

Returns a single matching window or `null`.

### `activate-window`

Brings the window to the foreground.  Includes a `ShowWindow +
SetForegroundWindow + SetWindowPos(TOP)` sequence for reliability
when called from a process that is not the current foreground.

### `minimize`, `maximize`, `restore`, `close-window`

Send the corresponding `WM_SYSCOMMAND` to the target window.

### `window-rect`

Returns `{left, top, right, bottom, width, height}`.

---

## UI Automation

All commands accept the standard window selectors (`--title`,
`--handle`, `--pid`) plus one or more of:

| Arg | Description |
|---|---|
| `--auto-id` | `AutomationId` (preferred) |
| `--control-type` | `Button`, `Edit`, `CheckBox`, ... (full list in `ui_find._CONTROL_TYPES`) |
| `--name` | Visible text / `Name` property |
| `--class-name` | Win32 class name |
| `--regex-name` | Treat `--name` as regex (uses pywinauto's `name_re`) |

You can use Microsoft Inspect.exe (bundled with Windows SDK) or
`pywinauto`'s `print_control_identifiers()` to discover these.

### `find-element`

```json
{"ok": true, "data": {
    "found": true,
    "auto_id": "FileNameControl",
    "control_type": "Edit",
    "name": "hello.txt",
    "class_name": "Edit",
    "rect": {"left": 350, "top": 220, "right": 760, "bottom": 245,
             "width": 410, "height": 25},
    "handle": 234567, "window_handle": 123456, "window_title": "Save As"
}}
```

### `click-element`

Adds `--button left|right|middle` and `--double`.

### `set-text`

`--value <text>` to write into the control.

### `element-text`

Returns the visible text (`Name`) of the element.

### `wait-element`

Polling version of `find-element`.  Extra args `--timeout` and
`--interval`.

---

## Image matching

All commands take `<template>` plus optional `--region` and
`--threshold`.

| Command | Notes |
|---|---|
| `find-image` | best match (default) or `--max-results N` for many |
| `click-image` | finds, then clicks the centre |
| `wait-image` | polls until found or `--timeout` |
| `count-image` | number of non-overlapping matches |

Templates should be PNG.  Resolution / DPI sensitive: capture the
template at the same DPI you will be matching against.  For
multi-monitor setups, capture on the same monitor.

---

## OCR (optional)

Requires the Tesseract 5 binary on `PATH` (or pass `--tesseract`
pointing at the exe).  Language packs are configured with `--lang`
(default `chi_sim+eng`).

### `ocr`

Returns plain text or `null` if Tesseract is unavailable.

### `ocr-words`

Returns per-word bounding boxes:

```json
{"ok": true, "data": [
    {"text": "确认", "x": 1280, "y": 712, "w": 36, "h": 22, "conf": 96.4},
    {"text": "Cancel", "x": 1340, "y": 712, "w": 60, "h": 20, "conf": 98.1}
]}
```

---

## Safety

### `emergency-stop`

Set the cross-process stop flag.  All subsequent actions abort.

### `clear-stop`

Reset the flag.

### `failsafe on|off`

Toggle pyautogui's mouse-to-corner abort.

### `stop-status`

```json
{"ok": true, "data": {"stopped": false, "failsafe": true}}
```