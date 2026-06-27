---
name: win-computer-use
description: "Windows desktop automation for AI agents. Load when the user asks to control a Windows desktop application, click buttons, type text, take screenshots, automate GUI tasks, or any native Windows app operation that cannot be done via browser automation."
agent_created: true
---

# win-computer-use

> **SPEED IS EVERYTHING.** Every API call = 1-3 seconds latency. A simple task must complete in **5-8 calls MAX**.
>
> If you find yourself making more than 8 calls for a single user action, **STOP and simplify**.

Windows desktop automation toolkit. Mirrors OpenAI Codex / Anthropic Claude's "computer use" capability — runs locally, no remote VM, no per-token cost.

## Installation

```bash
pip install win-computer-use
```

## ⚡ The Golden Path (READ THIS FIRST)

### Rule #1: One screenshot with markers → direct coordinates → done

**The fastest workflow for ANY task:**

```
Step 1: screenshot --with-markers  →  get full UI layout (1 call)
Step 2: click [coordinates]         →  act on what you see   (1 call)
Step 3: type / hotkey              →  input if needed        (1 call)
Done. 3 calls total.
```

### Rule #2: NEVER use OCR unless absolutely necessary

**OCR takes 5-10 seconds per call.** It is your LAST resort.
The `--with-markers` screenshot already tells you where everything is.

### Rule #3: Use raw coordinates when you can see the target in the screenshot

If the marker screenshot shows a button at (x, y), just `click x y`. Don't waste calls finding it again via UI Automation or image matching.

---

## Workflow Examples

### Example 1: Click taskbar icon & search (the user's actual test case)

**Task**: 点击任务栏 Everything 快捷方式 → 搜索 test.json → 右键进入目录

```
# Step 1: ONE screenshot with markers — see entire screen layout
win-computer-use screenshot --output logs/step1.png --with-markers
→ Returns image + JSON with all UI elements labeled

# Step 2: Click Everything icon on taskbar (read coordinates from step1 image)
win-computer-use click 850 1040
# (coordinates read from the marked screenshot)

# Step 3: Type search query directly
win-computer-use type "test.json"

# Step 4: Press Enter
win-computer-use key-press Return

# Step 5: Wait briefly for results, then right-click the file
win-computer-use wait 1
win-computer-use right-click 400 280
# (coordinate of search result from mental model of Everything UI)

# Step 6: Click "Open file location" in context menu
win-computer-use click 440 520
```

**Total: 6 calls. Done in ~10 seconds.**

Compare this to the BAD approach (what happened before): 40+ calls, 2+ minutes, massive token waste.

### Example 2: Open app & fill a form

```
# Step 1: Launch app
win-computer-use start-app --app "notepad"

# Step 2: Screenshot with markers
win-computer-use screenshot --output logs/form.png --with-markers

# Step 3: Click text area + type
win-computer-use click 500 400
win-computer-use type "Hello World"

# Step 4: Save
win-computer-use hotkey ctrl s
```

**Total: 4 calls.**

### Example 3: Complex multi-step (browser)

```
# Step 1: Screenshot current state
win-computer-use screenshot --output logs/start.png --with-markers

# Step 2: Activate browser window
win-computer-use activate-window --title "Edge"

# Step 3: Navigate (address bar shortcut)
win-computer-use hotkey ctrl l
win-computer-use type "https://www.bing.com"
win-computer-use key-press Return

# Step 4: Wait for page load, then screenshot results
win-computer-use wait 3
win-computer-use screenshot --output logs/results.png --with-markers

# Step 5: Click search box (from markers) and type
win-computer-use click 600 300
win-computer-use type "search query"
win-computer-use key-press Return
```

**Total: 7 calls.**

---

## Command Reference (Speed-Ordered)

### 🏆 Tier 1: Use these FIRST (fastest, most reliable)

| Command | When to use | Example |
|---------|------------|---------|
| `screenshot --with-markers` | **ALWAYS start here** — see full UI in one shot | `screenshot -o log.png --with-markers` |
| `click X Y` | You see target coordinates in screenshot | `click 500 300` |
| `right-click X Y` | Need context menu | `right-click 500 300` |
| `type TEXT` | Input text into focused field | `type "hello world"` |
| `hotkey KEY...` | Shortcut keys | `hotkey ctrl s` |
| `key-press KEY` | Single key | `key-press Return` |
| `start-app --app NAME` | Launch an app by name | `start-app --app msedge` |

### 🔶 Tier 2: Use when needed (moderate speed)

| Command | When to use | Example |
|---------|------------|---------|
| `activate-window --title X` | Bring window to front | `activate-window --title Edge` |
| `list-windows --filter X` | Find running windows | `list-windows --filter Edge` |
| `move X Y` | Move mouse without clicking | `move 100 100` |
| `double-click X Y` | Double-click | `double-click 500 300` |
| `drag X1 Y1 X2 Y2` | Drag from A to B | `drag 100 100 500 500` |
| `scroll N` | Scroll wheel | `scroll 3` |
| `wait SECONDS` | Pause for UI to load | `wait 2` |

### 🔴 Tier 3: Avoid unless necessary (slow or complex)

| Command | Why avoid | Alternative |
|---------|----------|-------------|
| `ocr` / `ocr-words` | **5-10 seconds per call!** | Use `--with-markers` instead |
| `find-element` | Needs exact control info | Read coords from marker screenshot |
| `click-element` | Same as above | Use `click X Y` |
| `find-image` | Needs template image prepared | Use `click X Y` from markers |
| `click-image` | Same as above | Use `click X Y` from markers |
| `smart-click` | Tries 3 methods sequentially (slow) | Use `click X Y` from markers |

### ⛑️ Safety (use only when needed)

| Command | Purpose |
|---------|---------|
| `emergency-stop` | Halt all operations immediately |
| `clear-stop` | Resume after emergency stop |
| `stop-status` | Check safety state |
| `failsafe on/off` | Toggle mouse-corner abort |

---

## Anti-Patterns (DO NOT DO These)

### ❌ Bad: OCR-heavy approach (SLOW)
```
# This took 40+ calls and 2+ minutes:
screenshot
ocr                                    # 10 seconds!
ocr-search "Everything"               # another 10 seconds!
find-element --name "Search"          # might not work
set-text --value "test.json"
screenshot                            # verify?
ocr                                    # ANOTHER scan?!
...
```

### ✅ Good: Marker-first approach (FAST)
```
# This completes in 6 calls and ~10 seconds:
screenshot --with-markers             # 1 call, see everything
click 850 1040                         # click taskbar icon
type "test.json"
key-press Return
wait 1
right-click 400 280                   # right-click result
click 440 520                         # open file location
```

### ❌ Bad: Over-investigating
```
# Don't try 5 different ways to find an app:
list-windows                          # try 1
find-window --title Everything        # try 2  
powershell get-process                # try 3
registry search                       # try 4
ocr search                            # try 5
```

### ✅ Good: Direct action
```
# Just click it if you can see it:
screenshot --with-markers            # see where things are
click X Y                             # done
```

---

## Calling Convention

```bash
# After pip install — use directly:
win-computer-use <command> [args...]

# Or via module:
python -m win_computer_use <command> [args...]
```

Every command emits a single JSON object on stdout:

```json
{"ok": true, "action": "screenshot", "data": {"path": "...", "width": 1920, "height": 1080}}
{"ok": false, "action": "click", "error": "..."}
```

Exit codes: `0` success, `1` error.

---

## Special Flags

| Flag | Effect | Use when |
|------|--------|----------|
| `--with-markers` | Annotate screenshot with UI element labels | **Always on first screenshot** |
| `--all-windows` | Scan ALL windows (not just active) | Target app is not foreground |
| `--base64` | Embed PNG as base64 in JSON | Passing image to vision LLM |
| `--region L,T,W,H` | Crop screenshot to region | Large screens / reduce token cost |
| `--lock-input` | Lock keyboard/mouse during command | Prevent user interference |
| `--lock-timeout SEC` | Auto-release lock after N seconds | Safety timeout |

---

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `COMPUTER_USE_SCREENSHOT_DIR` | `<skill>/screenshots/` | Auto-named screenshot output |
| `COMPUTER_USE_SAFETY_FILE` | `<skill>/logs/safety_state.json` | Emergency stop flag store |
| `COMPUTER_USE_MATCH_THRESHOLD` | `0.82` | Image match confidence floor |

## Dependencies

- Python 3.10+, Windows only
- `pyautogui`, `pywinauto`, `mss`, `opencv-python`, `numpy`, `Pillow`
- Optional: `uiautomation` (for `--with-markers`)
- Optional: `pytesseract` / `rapidocr` (for OCR — **avoid using**)

Install:
```bash
pip install win-computer-use
```

## Safety

This skill moves the cursor and types keys on the real computer.

- **FAILSAFE** enabled by default — slam cursor to top-left corner to abort
- **Emergency stop** — `emergency-stop` sets flag; next interactive call aborts
- Only invoke on actions the user explicitly authorised
