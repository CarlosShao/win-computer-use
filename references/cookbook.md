# workbuddy-computer-use — Cookbook

Step-by-step recipes for common automation scenarios.  Every recipe
assumes this skill lives at
`D:/work/java/AI-workspace/skills/.workbuddy/skills/workbuddy-computer-use`
and the venv is at `~/.workbuddy/binaries/python/envs/computer-use`.
Adjust paths as needed.

> Set up aliases at the top of any agent script:
> ```bash
> PY="C:/Users/swq/.workbuddy/binaries/python/envs/computer-use/Scripts/python.exe"
> CU="D:/work/java/AI-workspace/skills/.workbuddy/skills/workbuddy-computer-use/scripts/cli.py"
> "$PY" "$CU" --help
> ```

---

## 1. Open Notepad and type "hello world"

```bash
# Launch Notepad (Windows built-in).
cmd //c start notepad.exe
# Wait for the window to appear.
"$PY" "$CU" wait-element --title "Untitled - Notepad" \
    --control_type "Document" --timeout 5

# Bring it forward.
"$PY" "$CU" activate-window --title "Untitled - Notepad"

# Type.
"$PY" "$CU" type "hello world"
"$PY" "$CU" hotkey ctrl s
```

If the Document control cannot be found, fall back to:

```bash
# Click the text area roughly (use the screenshot to pick coords).
"$PY" "$CU" screenshot --output logs/notepad.png --base64
# Read coords from the screenshot the model returned.
"$PY" "$CU" click 400 300
"$PY" "$CU" type "hello world"
```

---

## 2. Fill a login form (username + password + click "Sign in")

```bash
"$PY" "$CU" click-element --title "Sign in to Acme" \
    --control_type Edit --auto_id "username" --value "alice"
# Or, with separate click + type:
"$PY" "$CU" click-element --title "Sign in to Acme" \
    --control_type Edit --auto_id "username"
"$PY" "$CU" type "alice"

"$PY" "$CU" click-element --title "Sign in to Acme" \
    --control_type Edit --auto_id "password"
"$PY" "$CU" type "$(cat ~/.config/acme-pass)"
"$PY" "$CU" key-press enter
```

---

## 3. Click "Confirm" buttons in a batch of dialogs

```bash
for i in $(seq 1 10); do
    "$PY" "$CU" click-image assets/confirm_button.png --threshold 0.85 \
        || break   # no more dialogs -> done
    "$PY" "$CU" wait 0.5
done
```

Capture the template once with the screenshot tool, save under
`assets/`.

---

## 4. Drive Excel from the command line

```bash
# Open a workbook.
"$PY" "$CU" click-image assets/excel_recent.png   # or use os.startfile
"$PY" "$CU" wait 2
"$PY" "$CU" activate-window --filter "Excel"

# Move to A1.
"$PY" "$CU" click-element --filter "Excel" \
    --control_type Edit --auto_id "A1NameBox"
"$PY" "$CU" type "A1"
"$PY" "$CU" key-press enter
"$PY" "$CU" type "1,2,3"
"$PY" "$CU" key-press enter
"$PY" "$CU" type "4,5,6"
```

---

## 5. Screenshot a specific region every N seconds (monitor)

```bash
while true; do
    "$PY" "$CU" screenshot --region 0,0,800,600 \
        --output "logs/monitor-$(date +%H%M%S).png"
    "$PY" "$CU" wait 5
done
```

Pipe `jq` to filter:
```bash
"$PY" "$CU" screenshot --base64 | jq -r '.data.base64' | base64 -d > shot.png
```

---

## 6. Read on-screen text (OCR)

```bash
"$PY" "$CU" ocr --region 100,100,600,200 --lang chi_sim+eng
```

Returns the recognised text or `null` if Tesseract isn't installed.

---

## 7. Find a button by image, log + click

```bash
"$PY" "$CU" find-image assets/ok_button.png --threshold 0.9 --max-results 5 \
    | jq '.data[] | {x: .x + .width/2, y: .y + .height/2, confidence}'
```

---

## 8. Abort a runaway loop with hotkey

Wire a watcher process that triggers `emergency-stop` when you press
`ctrl+alt+q` in a separate `cmd` window:

```bash
# One-off setup (Windows 10+): register an AutoHotkey script or use
# Windows shortcut "Ctrl+Alt+Q -> run cli.py emergency-stop".
# For tests, you can simply run from another shell:
"$PY" "$CU" emergency-stop
```

The next call to any interactive command in your loop will raise
`EmergencyStop` and exit 1 with the relevant JSON.

---

## 9. Switch language on a running app

```bash
# Press Windows+Space (or your keyboard switch key) and wait.
"$PY" "$CU" hotkey win space
"$PY" "$CU" wait 0.4
"$PY" "$CU" key-press enter
```

---

## 10. Driving an Electron / Qt app that hides automation IDs

When `find-element` returns nothing, the app likely exposes only the
top-level window.  Fall back to image matching:

```bash
"$PY" "$CU" click-image assets/feishu_new_message.png --threshold 0.88
```

Pair this with `wait-image` for state-dependent UI:

```bash
"$PY" "$CU" wait-image assets/login_succeeded.png --timeout 15 \
    || { echo "login failed"; "$PY" "$CU" emergency-stop; exit 1; }
```

---

## Tips & tricks

* **Run the venv Python explicitly.** Calling `python` directly from
  `execute_command` resolves to the wrong interpreter on most
  machines.  Always use the full path.
* **Pipe JSON to `jq`** for quick inspection:
  `"$PY" "$CU" list-windows | jq '.data | length'`
* **Capture screenshots into `logs/`** so they survive across calls
  and you can attach them to chat history.
* **Inspect windows** with `pywinauto`'s `print_control_identifiers()`
  via `python -c "..."` to discover auto IDs ahead of time.