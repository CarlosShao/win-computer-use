# workbuddy-computer-use — Troubleshooting

Common failures and how to recover.  Most issues fall into three
buckets: **environment**, **coordinates**, and **target application
quirks**.

---

## 1. `ImportError: No module named pyautogui` (or any other dep)

You're calling the system `python`, not the venv interpreter.

**Fix:** use the absolute path:

```bash
PY="C:/Users/swq/.workbuddy/binaries/python/envs/computer-use/Scripts/python.exe"
"$PY" scripts/cli.py --help
```

If the venv doesn't exist, recreate it:

```bash
"C:/Users/swq/.workbuddy/binaries/python/versions/3.13.12/python.exe" \
    -m venv "C:/Users/swq/.workbuddy/binaries/python/envs/computer-use"
"C:/Users/swq/.workbuddy/binaries/python/envs/computer-use/Scripts/python.exe" \
    -m pip install -r scripts/requirements.txt
```

---

## 2. `pyautogui.FailSafeException` mid-script

The cursor hit the top-left corner.  Either:

* Move the cursor away from (0,0) and rerun the failing step.
* Disable FAILSAFE temporarily with `cli.py failsafe off` (only for
  headless / VM scenarios where the corner can't be reached).

---

## 3. `click-element` returns `element not found`

Likely causes, in order of likelihood:

1. **Wrong `--auto-id` / `--name`.**  Inspect the window with
   `pywinauto`'s `print_control_identifiers()`:
   ```bash
   "$PY" -c "
   from pywinauto import Application
   app = Application(backend='uia').connect(title_re='.*Notepad.*')
   app.window(title_re='.*Notepad.*').print_control_identifiers()
   "
   ```
2. **Wrong backend.** Some apps only expose controls via Win32 (not
   UIA).  Switch pywinauto's backend by editing `ui_find._resolve_app`
   to use `backend="win32"`.
3. **Window handle stale.** Window handles are reused after the
   process exits.  Re-run `list-windows` and pass the fresh handle.
4. **App running as admin / different session.** UI Automation
   cannot cross session boundaries without
   `UIAccess="true"` in the manifest.  Run your script in the same
   integrity level as the target.

---

## 4. `find-image` returns nothing even though the template is on screen

* **Wrong DPI scale.** Re-capture the template at the same DPI as the
  current display.  Multi-monitor setups at mixed DPI are the most
  common cause.
* **Threshold too high.** Drop `--threshold` to `0.7` and see if any
  matches appear.  Animations and font hinting can drop the score.
* **Template includes anti-aliased edges.** Crop tightly to the
  non-edge pixels (e.g. remove a 1-pixel border) to reduce noise.
* **Wrong monitor.** `--region` is absolute screen coordinates; if
  your second monitor is at x=1920, that's where the search box
  lives, not at x=0.

---

## 5. `type` drops characters or prints garbage

* The first 200 chars of pure ASCII use `pyautogui.typewrite`.
  Anything else (Chinese, emoji, mixed) falls back to clipboard +
  `ctrl+v`.  Install `pyperclip` to ensure the fallback path works.
* Some apps swallow `SendInput` events when they don't have focus.
  Always `activate-window` first.
* For password fields or apps that disable clipboard paste, you must
  use ASCII `typewrite` and break the text into smaller chunks with
  a small `--interval`.

---

## 6. `activate-window` returns `{"ok": false, "error": "window not found"}`

* Window title changed (e.g. "Untitled - Notepad" becomes
  "hello.txt - Notepad" once saved).  Use `--filter` and regex.
* The window is owned by a different desktop / session.
* The window is owned by an elevated process and your agent is not
  elevated.  Re-run your agent as Administrator.

---

## 7. OCR returns `null`

* Tesseract binary not installed.  Download the Windows installer
  from https://github.com/UB-Mannheim/tesseract/wiki and tick "Add
  to PATH".
* Language pack missing.  Drop `chi_sim.traineddata` (and friends)
  into the `tessdata` folder next to `tesseract.exe`.
* Pass `--tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"`
  to override detection.

---

## 8. Slow screenshot (>300ms per call)

`mss` is the fastest pure-Python option, but on Windows you can do
better with the Windows.Graphics.Capture API.  Two routes:

* Accept the latency (still fast enough for ~5 Hz loops).
* Pre-capture into a fixed `--region` -- sub-regions are much cheaper
  than full screen on a 4K monitor.

---

## 9. `click_image` works once, then stops working

The template captured at a different DPI than the running app.  On
Windows laptops with dynamic DPI scaling this happens when the app
moves between a docked and undocked display.  Capture the template
on each display configuration or use the structured-UI path.

---

## 10. JSON output looks weird in Windows cmd

`cmd.exe` sometimes mangles UTF-8.  Run from Git Bash, PowerShell, or
pipe through `chcp 65001 > nul` first.

---

## Debugging checklist

When something fails unexpectedly, walk this list:

1. `cli.py screen-size` -- is the size what you expect?
2. `cli.py list-windows --filter <title>` -- is the window there?
3. `cli.py activate-window --title <title>` -- does the window come forward?
4. `cli.py screenshot --output logs/dbg.png` -- does the PNG show the
   state you expect?
5. `cli.py pixel <x> <y>` -- is the colour at the click target what
   the template expects?
6. `cli.py find-element --title <title> --auto_id <id>` -- is the
   control reachable?
7. `cli.py find-image assets/x.png --threshold 0.5` -- does any
   match show up at a low threshold?

If all seven succeed, the failing step is almost certainly a typo
or off-by-one in coordinates.