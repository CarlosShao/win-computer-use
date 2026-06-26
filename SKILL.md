---
name: workbuddy-computer-use
description: "This skill should be used when the user asks WorkBuddy to control a Windows desktop application -- clicking buttons, typing into text fields, taking screenshots, switching windows, finding UI elements, matching on-screen images, or running OCR. It mirrors the Codex / Hermes 'computer use' capability surface and works on any Win32 / WinForms / WPF / Qt / Electron application via mouse + keyboard simulation, structured UI Automation (pywinauto), and OpenCV template matching. Load it whenever the user says things like '帮我打开 XX 程序', '自动点这个按钮', '截个图', '找一下屏幕上的 XX 图标', '操控这个 app', '填这个表单', 'read the screen', 'operate this GUI', or asks for any task that requires actually driving a desktop app instead of just calling its API."
agent_created: true
---

# workbuddy-computer-use

Windows desktop automation toolkit for WorkBuddy.  A drop-in replacement
for the "computer use" capability exposed by OpenAI Codex and Hermes /
Anthropic Claude -- but driven entirely from Python running on the
user's machine, no remote VM, no per-token cost.

## What it can do

| Capability | Commands |
|---|---|
| **Screenshot** | `screenshot`, `screen-size`, `pixel` |
| **Mouse** | `mouse-position`, `move`, `click`, `double-click`, `right-click`, `drag`, `scroll` |
| **Keyboard** | `type`, `hotkey`, `key-press`, `key-down`, `key-up`, `wait` |
| **Window mgmt** | `list-windows`, `find-window`, `activate-window`, `minimize`, `maximize`, `restore`, `close-window`, `window-rect` |
| **Structured UI** | `find-element`, `click-element`, `set-text`, `element-text`, `wait-element` |
| **Image match** | `find-image`, `click-image`, `wait-image`, `count-image` |
| **OCR (optional)** | `ocr`, `ocr-words` (requires Tesseract binary on PATH) |
| **Safety** | `emergency-stop`, `clear-stop`, `failsafe`, `stop-status` |

## When to load this skill

Load it the moment the user asks for anything that requires touching a
desktop app.  Concrete trigger phrases include:

- "帮我打开 XX 程序并点确定"
- "自动填这个表单"
- "截个图给我看"
- "find the Settings button and click it"
- "drive this GUI for me"
- "屏幕上的 XX 图标在哪?"
- "把这段文字输入到记事本"
- "operate Excel / 钉钉 / 企业微信 / 飞书 / 浏览器 ... "
- "playwright is not enough, this is a native app"
- "codex computer use" / "Hermes computer use"
- "我手动操作太烦了, 帮我自动化一下"

If the user is asking only about a **browser** (Chrome / Edge / QQ
browser), prefer the dedicated `browser-use` skill -- it has tighter
selectors and works in headless mode.  This skill is for **native
Windows apps** and for any task where the browser skills can't reach
the UI.

## Workflow

### 1. Locate / open the target application

Prefer the structured UI Automation path whenever possible -- it is
far more robust than pixel clicking.  Start by listing windows:

```bash
python scripts/cli.py list-windows --filter "Notepad"
```

The returned JSON contains ``title``, ``handle``, ``pid`` and
``rect``.  Activate it with:

```bash
python scripts/cli.py activate-window --title "Untitled - Notepad"
```

If the application is not running, ask the user (or the LLM) to start
it via the standard Windows shell (`start notepad`, `os.startfile`,
or just clicking the Start Menu).

### 2. Take a screenshot to ground the model

```bash
python scripts/cli.py screenshot --output logs/last.png --base64
```

`--base64` embeds the PNG inline so the LLM can pipe it straight into
a vision model.  For large screens or repetitive workflows, prefer
cropping with `--region left,top,width,height` to keep image size and
token cost down.

### 3. Drive the UI

**Preferred**: structured lookup.

```bash
# Find a button by its automation id (visible in tools like Inspect.exe).
python scripts/cli.py find-element --title "Untitled - Notepad" \
    --control_type Button --auto_id "Open"
# Click it.
python scripts/cli.py click-element --title "Untitled - Notepad" \
    --control_type Button --name "OK"
# Type into a text field.
python scripts/cli.py set-text --title "Save As" \
    --control_type Edit --auto_id "FileNameControl" --value "report.txt"
```

**Fallback 1**: image matching when the target is canvas-rendered
(games, custom-painted widgets, Electron apps without proper
automation IDs):

```bash
python scripts/cli.py click-image assets/ok_button.png --threshold 0.85
```

**Fallback 2**: raw coordinates after inspecting the screenshot:

```bash
python scripts/cli.py click 1240 712
python scripts/cli.py type "Hello, world!"
```

### 4. Loop safely

For repetitive workflows, batch the commands in a small Bash script
inside the skill's `logs/` folder so the model only invokes a single
`execute_command` per iteration.  Always include an emergency-stop
branch:

```bash
python scripts/cli.py click-image assets/confirm.png \
    || python scripts/cli.py emergency-stop
```

### 5. Stop / undo

- `python scripts/cli.py emergency-stop` -- set the stop flag; the
  *next* call to any action raises `EmergencyStop` immediately.
- `python scripts/cli.py clear-stop` -- clear the flag (e.g. before
  retrying after a fix).
- `python scripts/cli.py failsafe off` -- disable the
  mouse-to-top-left-corner abort (useful inside RDP / VMs where
  the cursor can't reach the corner).  Off by default for typical
  desktop use: keep `on`.
- `python scripts/cli.py stop-status` -- query both flags.

## Calling convention

All commands share a single Python entry point.  The canonical
invocation from WorkBuddy's `execute_command` is:

```bash
PY="C:/Users/swq/.workbuddy/binaries/python/envs/computer-use/Scripts/python.exe"
SKILL="D:/work/java/AI-workspace/skills/.workbuddy/skills/workbuddy-computer-use"
"$PY" "$SKILL/scripts/cli.py" <command> [args...]
```

Every command emits a single JSON object on stdout:

```json
{"ok": true, "action": "screenshot", "data": {"path": "...", "width": 1920, "height": 1080, ...}}
{"ok": false, "action": "click_element", "error": "element not found", "traceback": "..."}
```

Exit codes: `0` on success, `1` on error.  Pipe failures (`||` chains,
`jq -e .ok`) work as expected.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `COMPUTER_USE_SCREENSHOT_DIR` | `<skill>/screenshots/` | Where to drop auto-named screenshots |
| `COMPUTER_USE_SAFETY_FILE` | `<skill>/logs/safety_state.json` | Cross-process safety flag store |
| `COMPUTER_USE_MATCH_THRESHOLD` | `0.82` | OpenCV `matchTemplate` confidence floor |

Set `TESSDATA_PREFIX` if your Tesseract install lives outside the
default location.

## Dependencies

- Python 3.10+ (tested on 3.13.12)
- `pyautogui`, `pywinauto`, `mss`, `opencv-python`, `numpy`, `Pillow`,
  `pygetwindow`, `comtypes`, `pyperclip`
- Optional: `pytesseract` + Tesseract 5 binary (for OCR)
- Optional: `pyperclip` (for non-ASCII `type`)

Install with the bundled `scripts/requirements.txt`:

```bash
python -m pip install -r scripts/requirements.txt
```

## Safety

This skill literally moves the cursor and types keys on the user's
physical computer.  Treat every command as if you were sitting at the
keyboard yourself.

- **FAILSAFE** is enabled by default.  Slam the cursor into the
  top-left corner of the primary monitor and every subsequent call
  raises `pyautogui.FailSafeException`.
- **Emergency stop** sets a flag in `logs/safety_state.json`.  Any
  running command that calls `safety.check_emergency_stop()` (i.e.
  every interactive action in this skill) aborts on the next poll.
  Trigger it with `cli.py emergency-stop` from another shell, or via
  a hotkey wired to a future `cmd_watchdog.py`.
- **Permission scope.** This skill does not require admin rights, but
  it can drive any GUI the user can drive -- including file-system
  dialogs, password managers, payment apps.  Only invoke it on
  commands the user explicitly authorised.

## Layout

```
workbuddy-computer-use/
├── SKILL.md                          # this file
├── scripts/                          # the actual Python toolkit
│   ├── platform.py                   #   OS / DPI helpers
│   ├── screen.py                     #   screenshot primitives
│   ├── input_control.py              #   mouse + keyboard
│   ├── window_mgmt.py                #   window list / activate
│   ├── ui_find.py                    #   structured UI Automation
│   ├── image_match.py                #   OpenCV template matching
│   ├── ocr.py                        #   Tesseract (optional)
│   ├── safety.py                     #   FAILSAFE + emergency stop
│   ├── cli.py                        #   JSON CLI entry point
│   └── requirements.txt
├── references/
│   ├── api.md                        # full API reference
│   ├── cookbook.md                   # step-by-step recipes
│   └── troubleshooting.md            # common errors + fixes
├── assets/                           # template images for click-image
├── screenshots/                      # auto-named screenshots
└── logs/                             # safety state + run logs
```

For full parameter docs and worked examples, see
[`references/api.md`](references/api.md) and
[`references/cookbook.md`](references/cookbook.md).  When something
breaks unexpectedly, check [`references/troubleshooting.md`](references/troubleshooting.md)
first.