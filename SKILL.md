---
name: win-computer-use
description: "Windows desktop automation for AI agents. Load when the user asks to control a Windows desktop application, click buttons, type text, take screenshots, automate GUI tasks, or any native Windows app operation that cannot be done via browser automation."
agent_created: true
---

# win-computer-use

> **SPEED IS EVERYTHING.** Every API call = 1-3s latency + token cost.  
> **Simple task ≤ 5 calls. Complex task ≤ 10 calls.**  
> If you exceed the budget, you are doing it wrong — stop and simplify.

Windows desktop automation toolkit — local, no VM, no per-token cost.

## Installation

```bash
pip install win-computer-use
```

---

## ⚡ The Only Workflow (Plan-First)

**One screenshot → plan ALL clicks → execute in batch → done.**

```
Step 1: screenshot --with-markers    # ONE shot, see ALL elements (1 call)
Step 2: click / type / key-press     # execute planned actions (2-4 calls)
Done. 3-5 calls total.
```

> **Never screenshot-mid-task.** If you need coordinates again, re-read the same marker screenshot. It's still valid — the UI didn't move in 2 seconds.

### For Electron apps (Bruno, VS Code, etc.)

These apps don't expose elements to UI Automation. `--with-markers` falls back to OCR automatically in a single call — the text labels are included in the returned JSON. **No extra OCR call needed.**

### No Wait

Never use `wait`. Click immediately after the previous action completes. Bruno/Everything/Windows respond fast enough. If you need to wait for a specific element, use `wait-element` (polls, not fixed delay).

---

## Workflow Examples

### Example 1: Click taskbar icon & search (Bruno launch test)

**Task**: 点击任务栏 Everything → 搜索 test.json → 右键进入目录

```
# Step 1: ONE screenshot — see taskbar + everything
win-computer-use screenshot --output logs/s1.png --with-markers
→ Returns JSON with 50 labeled elements + marked image

# Step 2-5: Execute all actions (no intermediate checks)
win-computer-use click 850 1040           # click Everything on taskbar
win-computer-use type "test.json"          # search query
win-computer-use key-press Down            # select first result
win-computer-use hotkey shift f10          # context menu
win-computer-use type "o"                  # "Open file location" accelerator

# OR simpler: Ctrl+Shift+Enter directly opens file path:
win-computer-use hotkey ctrl shift enter

# Verify: check if File Explorer opened
win-computer-use list-windows --filter "explorer"
```

**3-5 calls. Done in ~5 seconds.**

### Example 2: Open Bruno → navigate API → Send request

**Task**: 打开 Bruno → 找到 TestApiRemaining → 发送 Minimax remaining 请求

```
# Step 1: Launch + screenshot
win-computer-use screenshot --output logs/s1.png --with-markers
→ Returns JSON. Find Bruno desktop shortcut coords + all UI elements + OCR text

# Step 2-5: Execute planned actions in one batch
win-computer-use double-click 38 518       # launch Bruno from desktop
win-computer-use click 500 880              # expand TestApiRemaining collection
win-computer-use click 764 534              # click Minimax remaining API
win-computer-use click 1955 583             # Send the request

# Verify
win-computer-use screenshot --region 1300,620,420,600 --output logs/response.png
```

**5 calls. Done in ~8 seconds.** (vs. 15 calls / 44s before optimization)

### Example 3: Complex browser workflow

```
# Step 1: Full layout
win-computer-use screenshot --output logs/s1.png --with-markers

# Step 2-6: Execute
win-computer-use activate-window --title Edge
win-computer-use hotkey ctrl l
win-computer-use type "https://www.bing.com"
win-computer-use key-press Return
win-computer-use wait-element --title Bing --timeout 5
win-computer-use screenshot --output logs/results.png --with-markers
```

**6 calls.**

---

## Command Reference

### 🏆 Tier 1: Fastest (use every time)

| Command | Example |
|---------|---------|
| `screenshot --with-markers` | `screenshot -o s1.png --with-markers` |
| `click X Y` | `click 500 300` |
| `right-click X Y` | `right-click 500 300` |
| `type "text"` | `type "search query"` |
| `hotkey ctrl s` | `hotkey ctrl shift enter` |
| `key-press Return` | `key-press Down` |
| `start-app --app name` | `start-app --app bruno` |

### 🔶 Tier 2: Moderate speed (use when needed)

| Command | Example |
|---------|---------|
| `activate-window --title X` | `activate-window --title Edge` |
| `list-windows --filter X` | `list-windows --filter explorer` |
| `double-click X Y` | `double-click 38 518` |
| `wait-element --title X --timeout 5` | `wait-element --title Bruno --timeout 5` |

### 🔴 Tier 3: Slow (avoid)
**OCR**: 5-10s per call. Don't use. `--with-markers` now includes OCR text for Electron apps.  
**find-element / click-element**: Only use when markers fail.  
**find-image / click-image**: Only if you have a template image.

---

## Anti-Patterns

❌ **Don't do this (slow):**
```
screenshot → think → ocr → think → click → screenshot → ocr → think → click → ...
```

✅ **Do this (fast):**
```
screenshot (see everything) → click → click → type → done
```

❌ **Don't wait artificially:** `wait 3`, `wait 5` — waste 3-5s each time.  
✅ **Click immediately or use `wait-element`.**

❌ **Don't screenshot between every action.** UI doesn't change in 2 seconds.  
✅ **One screenshot at start, plan all actions.**

❌ **Don't try 5 ways to find an app.**  
✅ **Just click the coordinates you already saw.**

---

## Calling Convention

```bash
win-computer-use <command> [args...]
```

Every command emits JSON on stdout: `{"ok": true/false, "action": "...", "data": {...}}`

### Performance Budget per Task

| Task complexity | Max calls | Target time |
|----------------|-----------|-------------|
| Simple (single click/type) | 3 | ≤ 3s |
| Medium (launch app + interact) | 5 | ≤ 8s |
| Complex (navigate multi-step) | 10 | ≤ 20s |

## Safety

- **FAILSAFE**: enabled by default — mouse to screen corner = abort
- **Emergency stop**: `emergency-stop` flags next command
- This tool controls your real mouse & keyboard. Only use on authorized actions.
