# win-computer-use

Windows 桌面自动化工具包 — 让 AI Agent 像人一样操控 Windows 桌面应用。

[English](#english)

> [!WARNING]
> **本工具不是安装即用！** 需要本地 Python 环境（≥ 3.10）+ 依赖安装。
> 详见下方 [环境要求](#安装)。

> [!IMPORTANT]
> **Windows Only！** 本工具依赖 `pywinauto`（Windows UI Automation），**不支持 macOS / Linux**。

---

## 这是什么？

对标 OpenAI Codex / Anthropic Claude 的 **Computer Use** 能力，但是：

- ✅ **跑在你自己的 Windows 机器上**，不需要远程 VM
- ✅ **零按 token 计费**，截图/操作不限次数
- ✅ **支持中文输入**（通过剪贴板）
- ✅ **支持任意 Windows 应用**：Win32 / WinForms / WPF / Qt / Electron / UWP

当 AI Agent 遇到浏览器覆盖不到的场景（原生桌面应用），可加载本工具进行自动化操作。

---

## 能做什么？

| 能力 | 典型命令 |
|------|---------|
| 📸 **截图** | 全屏截图、区域截图、返回 base64 |
| 🖱️ **鼠标** | 移动、单击、双击、右键、拖拽、滚轮 |
| ⌨️ **键盘** | 输入文本（含中文）、组合快捷键、按键按下/抬起 |
| 🪟 **窗口管理** | 列出所有窗口、激活、最小化、最大化、关闭 |
| 🔍 **UI 自动化** | 按控件名/类型查找元素、点击、填文本、等待元素出现 |
| 🖼️ **图像模板匹配** | OpenCV 找图、点击图标、等待图像出现（NMS 去重） |
| 🔤 **OCR（可选）** | 屏幕文字识别（需安装 Tesseract） |
| 🛡️ **安全机制** | Emergency Stop、Failsafe（鼠标甩到角落急停） |

---

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/CarlosShao/win-computer-use.git
cd win-computer-use
```

### 2. 创建虚拟环境并安装依赖（Windows）

```bash
# 进入工具目录
cd win-computer-use

# 创建隔离虚拟环境
python -m venv .venv

# 安装依赖（仅 Windows）
.venv\Scripts\pip.exe install pyautogui pywinauto opencv-python numpy mss pillow pytesseract rapidocr-onnxruntime
```

> **注意**：Python 版本要求 ≥ 3.10。如果系统没有 `python` 命令，请用 `python3` 替代。
> 
> ⚠️ **本工具仅支持 Windows**，`pywinauto` 是 Windows 专属依赖，无法在 macOS / Linux 上运行。
> 
> **OCR 说明**：默认使用 **RapidOCR** 后端（无需安装 Tesseract），首次运行会自动下载模型（~40MB）。如需使用 Tesseract，可加 `--backend tesseract` 参数。

### 3.（可选）安装 Tesseract OCR

如果需要 OCR 功能：

- 下载：https://github.com/UB-Mannheim/tesseract/wiki
- 安装后确保 `tesseract` 命令在 PATH 中
- 中文语言包确认：`tesseract --list-langs` 含 `chi_sim`

---

## 使用示例

### 示例 1：自动填表（记事本）

```
用户：帮我在记事本里输入"你好世界"，然后保存为 test.txt
```

AI 加载本工具后自动执行：
1. `list-windows` 找到记事本
2. `activate-window` 激活窗口
3. `type "你好世界"` 输入中文
4. `hotkey ctrl s` 触发保存
5. `set-text` 填文件名
6. `click-element` 点保存按钮

### 示例 2：找图点击

```
用户：屏幕上有个"确定"按钮的图标，帮我找到并点击它
```

1. 先从截图中裁剪出"确定"图标另存为 `ok_btn.png`
2. `find-image ok_btn.png` → 返回坐标
3. `click-image ok_btn.png` → 自动移动鼠标并点击

### 示例 3：UI Automation（计算器）

```
用户：打开计算器，算一下 123 * 456
```

1. `find-window --title "计算器"` 找窗口
2. `find-element --title "计算器" --control_type Button --name "一"` 找按钮
3. `click-element` 依次点击数字和运算符
4. `element-text` 读取结果

---

## CLI 全命令参考

<details>
<summary>点击展开全部命令</summary>

```bash
python cli.py --help

# 截图
screenshot --output <path> [--base64]
screen-size
pixel --x <n> --y <n>

# 鼠标
mouse-position
move --x <n> --y <n> [--duration <s>]
click [--x <n> --y <n>] [--button left|middle|right]
double-click [--x <n> --y <n>]
right-click [--x <n> --y <n>]
drag --x1 <n> --y1 <n> --x2 <n> --y2 <n>
scroll [--clicks <n>] [--x <n> --y <n>]

# 键盘
type --text <str>
hotkey <key1> [key2 ...]
key-press --key <str>
key-down --key <str>
key-up --key <str>
wait [--seconds <n>]

# 窗口
list-windows [--filter <str>]
find-window --title <str>
activate-window --title <str>
minimize --title <str>
maximize --title <str>
restore --title <str>
close-window --title <str>
window-rect --title <str>

# UI Automation (pywinauto)
find-element --title <str> --control_type <str> [--name <str>] [--auto_id <str>]
click-element ...
set-text --title <str> --control_type <str> --auto_id <str> --value <str>
element-text ...
wait-element ...

# 图像匹配 (OpenCV)
find-image <template_path> [--threshold <0-1>] [--region x,y,w,h]
click-image <template_path> [--threshold <0-1>]
wait-image <template_path> [--timeout <s>]
count-image <template_path> [--threshold <0-1>]

# OCR (需 Tesseract)
ocr [--region x,y,w,h]
ocr-words [--region x,y,w,h]

# 安全
emergency-stop
clear-stop
failsafe [on|off]
stop-status
```

</details>

---

## 安全机制

| 机制 | 说明 |
|------|------|
| **Emergency Stop** | 调用后所有操作命令被拒绝，直到 `clear-stop` |
| **Failsafe** | 鼠标快速甩到屏幕四角任一角，立即终止所有进行中的操作 |
| **坐标越界保护** | 所有鼠标移动前校验坐标在屏幕范围内 |

---

## 测试

本仓库包含 `TEST_PLAN.md`，覆盖 Lv1（冒烟）→ Lv5（安全+E2E）共 55+ 测试用例。

建议逐级执行，确认每级通过后再正式使用或发布。

---

## 技术栈

- **PyAutoGUI** — 鼠标/键盘底层控制
- **OpenCV (cv2)** — 图像模板匹配 + NMS 去重
- **pywinauto** — Windows UI Automation（控件树遍历）
- **mss** — 高性能截图（比 PyAutoGUI 快 3-5x）
- **pytesseract** — OCR（可选，需 Tesseract 二进制）
- **Pillow** — 图像处理

---

## License

[MIT](LICENSE)

---

## English

> [!WARNING]
> **Not an install-and-use tool!** Requires Python (>= 3.10) + pip dependencies on your local machine.
> See [environment setup](#install) below.

> [!IMPORTANT]
> **Windows Only!** This tool depends on `pywinauto` (Windows UI Automation) and **does not support macOS / Linux**.

## What is this?

A Windows desktop automation toolkit that mirrors the "Computer Use" capability of OpenAI Codex / Anthropic Claude — but runs entirely on **your own Windows machine**, no remote VM, no per-token cost.

**Supports any Windows app**: Win32, WinForms, WPF, Qt, Electron, UWP.

### Features

- Screenshot (mss, 3-5x faster than PyAutoGUI)
- Mouse control (move, click, drag, scroll)
- Keyboard input (supports **Chinese** via clipboard)
- Window management (list, activate, minimize, close)
- UI Automation via pywinauto (find elements by name/automation id)
- OpenCV template matching with NMS (Non-Maximum Suppression)
- OCR via Tesseract (optional)
- Safety: emergency stop + failsafe (mouse corner kill switch)

### Install (Windows Only)

```bash
git clone https://github.com/CarlosShao/win-computer-use.git
cd win-computer-use
python -m venv .venv

# Install Python deps (Windows only)
.venv\Scripts\pip.exe install pyautogui pywinauto opencv-python numpy mss pillow pytesseract rapidocr-onnxruntime
```

> **Note**: Requires Python >= 3.10. Use `python3` if `python` is not available.
> 
> ⚠️ **Windows Only!** `pywinauto` is Windows-specific and will not work on macOS / Linux.
> 
> **OCR**: Uses **RapidOCR** by default (no Tesseract needed). Models auto-download on first use (~40MB). Use `--backend tesseract` to switch.

### Quick Start

```
User: Open Notepad, type "hello world", and save as test.txt
```

The agent will auto-load this toolkit and execute the full desktop automation flow.

### Links

- GitHub: https://github.com/CarlosShao/win-computer-use
- Issues: https://github.com/CarlosShao/win-computer-use/issues
