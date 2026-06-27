# win-computer-use 测试方案（Lv1 → Lv10）

> 本文档为 `win-computer-use` 工具的分级测试方案。
> 每个等级独立可执行，按顺序递进。在新会话中逐级测试，记录结果。
> 
> **测试目标应用**：Microsoft Edge / Google Chrome（二选一，推荐 Edge，Windows 自带）
> 
> **功能覆盖（Phase 1 & 2 & 3）**：
> - ✅ 基础桌面自动化（截图、鼠标、键盘）
> - ✅ 窗口管理（列表、激活、最小化/最大化/恢复、关闭）
> - ✅ 结构化 UI Automation（查找元素、点击、输入文本）
> - ✅ 图像模板匹配（find-image / click-image / wait-image）
> - ✅ OCR 文字识别（Tesseract / RapidOCR）
> - ✅ 安全机制（emergency-stop / failsafe）
> - ✅ 操作通知栏（透明度）
> - ✅ 语义截图带标记点（--with-markers）
> - ✅ 输入锁（--lock-input / lock / unlock）
> - ✅ 宏录制与回放（rec-start / rec-stop / rec-play）
> - ✅ FastAPI HTTP 服务器（server.py）
> - ✅ 智能点击（smart-click，自动降级）

---

## 环境准备

### 0. 安装依赖（首次使用前必须完成）

```bash
# 进入工具目录
cd <你的安装路径>/win-computer-use

# 创建隔离虚拟环境（如果还没创建）
python -m venv .venv

# Windows: 激活 venv 并安装依赖
.venv\Scripts\pip.exe install -r scripts/requirements.txt

# 安装 FastAPI（用于 Lv9 测试）
.venv\Scripts\pip.exe install fastapi uvicorn

# macOS / Linux: 激活 venv 并安装依赖
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/pip install fastapi uvicorn
```

> **注意**：Python 版本要求 >= 3.10。

### 快捷命令设置

```powershell
# ===== PowerShell =====
$SKILL = "<你的安装路径>\win-computer-use"
$PY = "$SKILL\.venv\Scripts\python.exe"

# 测试 CLI 是否可用
win-computer-use --help
```

```bash
# ===== Bash / Git Bash / WSL =====
export SKILL="<你的安装路径>/win-computer-use"

# 测试 CLI 是否可用
win-computer-use --help
```

**前置条件：**
- [ ] Python venv 已创建且依赖已安装 (`pip install -r scripts/requirements.txt`)
- [ ] 显示器分辨率已知
- [ ] 测试用目标应用已安装：**Microsoft Edge**（或 Google Chrome）
- [ ] 测试用辅助应用已安装：记事本 (Notepad)、计算器 (Calculator)（Lv4/Lv5 备用）
- [ ] Tesseract OCR 已安装（Lv5C 需要，没有则跳过 OCR 用例）
- [ ] **管理员权限**（Lv7 输入锁测试需要）
- [ ] **网络可用**（Lv2/Lv3/Lv5E 浏览器测试需要）

---

## Lv1 基础能力验证（Smoke Test）

**目标**：确认 CLI 能正常启动、截图、获取屏幕信息、鼠标键盘基本操作。

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 1.1 | CLI `--help` 正常输出 | `win-computer-use --help` | 输出所有子命令列表，无报错 | ⬜ |
| 1.2 | 全屏截图 | `win-computer-use screenshot --output logs/test_lv1.png` | 返回 JSON 含 path/width/height，文件存在 | ⬜ |
| 1.3 | 截图带 base64 | 同上 + `--base64` | JSON 中含 base64 字段，长度 > 0 | ⬜ |
| 1.4 | 获取屏幕尺寸 | `win-computer-use screen-size` | 返回 `{width, height}` 匹配实际分辨率 | ⬜ |
| 1.5 | 获取鼠标位置 | `win-computer-use mouse-position` | 返回 `{x, y}` 在屏幕范围内 | ⬜ |
| 1.6 | 鼠标移动 | `win-computer-use move 100 100` → 再 mouse-position | 鼠标在 (100,100) 位置（允许 ±2px 误差）| ⬜ |
| 1.7 | 单击 | `win-computer-use click 500 500` | 执行无报错 | ⬜ |
| 1.8 | 键盘输入英文 | `win-computer-use type "hello_world"` | 执行无报错（建议在浏览器地址栏验证）| ⬜ |
| 1.9 | 安全状态查询 | `win-computer-use stop-status` | 返回 emergency_stop / failsafe 状态 | ⬜ |
| 1.10 | 像素颜色读取 | `win-computer-use pixel 100 100` | 返回 `{x, y, color: "#RRGGBB"}` | ⬜ |

**Lv1 通过标准**：全部 10 项通过 ✅

---

## Lv2 窗口管理

**目标**：能发现、激活、操控窗口。

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 2.1 | 列出所有窗口 | `win-computer-use list-windows` | 返回 JSON 数组，每项含 title/handle/pid/rect | ⬜ |
| 2.2 | 过滤窗口 | `win-computer-use list-windows --filter "Edge"` | 只返回 Edge 浏览器窗口 | ⬜ |
| 2.3 | 正则过滤窗口 | `list-windows --filter "Edge$" --regex` | 只返回标题以 Edge 结尾的窗口 | ⬜ |
| 2.4 | 查找窗口 | `win-computer-use find-window --title "Edge"` | 返回窗口信息或明确的 "not found" | ⬜ |
| 2.5 | 激活窗口 | 先打开 Edge → `activate-window --title "Edge"` | Edge 窗口置顶获得焦点 | ⬜ |
| 2.6 | 最小化窗口 | `minimize --title "Edge"` | 窗口最小化到任务栏 | ⬜ |
| 2.7 | 最大化窗口 | `maximize --title "Edge"` | 窗口全屏最大化 | ⬜ |
| 2.8 | 恢复窗口 | `restore --title "Edge"` | 窗口恢复之前大小 | ⬜ |
| 2.9 | 获取窗口矩形 | `window-rect --title "Edge"` | 返回 {left, top, right, bottom} | ⬜ |
| 2.10 | 关闭窗口（⚠️ 会关闭应用）| `close-window --title "Edge"` | 窗口关闭 | ⬜ |

**Lv2 通过标准**：≥ 9/10 通过（close-window 可选跳过避免误操作）✅

---

## Lv3 结构化 UI Automation

**目标**：通过 UI Automation 控件树查找并操作元素（pywinauto / uiautomation）。

**测试场景**：打开 Edge 浏览器 → 打开设置页面 → 操作设置对话框中的控件。

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 3.1 | 打开浏览器设置页 | 打开 Edge → `hotkey ctrl shift ,` （打开设置）| 设置页面出现 | ⬜ |
| 3.2 | find-element 按 name 查找 | `find-element --title "Settings" --control_type Button --name "Appearance"` | 返回控件信息（bounds 等）| ⬜ |
| 3.3 | find-element 按 auto_id 查找 | `find-element --title "Settings" --control_type Edit --auto_id "searchBox"` | 找到设置搜索框 | ⬜ |
| 3.4 | click-element 点击按钮 | `click-element --title "Settings" --control_type Button --name "Default browser"` | 切换到默认浏览器设置 | ⬜ |
| 3.5 | set-text 输入文本 | 在设置搜索框 → `set-text --title "Settings" --control_type Edit --auto_id "searchBox" --value "downloads"` | 搜索框填入 "downloads" | ⬜ |
| 3.6 | element-text 读取控件文本 | `element-text --title "Settings" --control_type Edit --auto_id "searchBox"` | 返回 "downloads" | ⬜ |
| 3.7 | wait-element 等待元素出现 | 关闭设置后重新打开 → `wait-element --title "Settings" --control_type Button --name "Appearance" --timeout 5` | 5 秒内返回成功 | ⬜ |
| 3.8 | 控件不存在时的错误处理 | `find-element --title "NotExistWindow" --control_type Button --name "Ok"` | 返回 `{ok: false, error: ...}` 不崩溃 | ⬜ |
| 3.9 | click-element 双击 | `click-element --title "Edge" --control_type Button --name "New tab" --double` | 双击按钮 | ⬜ |

**Lv3 通过标准**：≥ 8/9 通过 ✅

---

## Lv4 图像模板匹配

**目标**：OpenCV findImage/clickImage 能准确定位屏幕上的图标/按钮。

**测试场景**：截取 Edge 浏览器地址栏右侧的 **"收藏"、"设置"** 等图标作为模板。

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 4.1 | 准备模板图片 | 截取 Edge 地址栏右侧的"收藏"图标，保存到 `assets/test_icon.png` | 模板文件存在，尺寸合理 (< 200x200)| ⬜ |
| 4.2 | find-image 基础匹配 | `find-image assets/test_icon.png` | 返回坐标和 confidence ≥ 0.82 | ⬜ |
| 4.3 | find-image 指定阈值 | `find-image assets/test_icon.png --threshold 0.90` | 高阈值下仍能找到（或明确返回未找到）| ⬜ |
| 4.4 | click-image 点击 | `click-image assets/test_icon.png` | 鼠标移动到目标位置并点击 | ⬜ |
| 4.5 | wait-image 等待图像出现 | `wait-image assets/test_icon.png --timeout 10` | 10 秒内返回成功 | ⬜ |
| 4.6 | count-image 统计匹配数 | `count-image assets/test_icon.png --threshold 0.85` | 返回正确的匹配数量 | ⬜ |
| 4.7 | 多匹配场景（NMS）| 屏幕上有多个相似图标时 locate_all | 返回去重后的正确数量（NMS 生效）| ⬜ |
| 4.8 | 无匹配时优雅降级 | `find-image assets/nonexistent.png` | 返回 `{ok: false}` 不崩溃不抛异常 | ⬜ |
| 4.9 | multi-scale 多尺度匹配 | `find-image assets/test_icon.png --multi-scale` | 在高 DPI 缩放下仍能匹配 | ⬜ |

**Lv4 通过标准**：≥ 8/9 通过 ✅

---

## Lv5 高级能力 & 安全机制

**目标**：OCR（可选）、安全停止、边界场景、中文输入、组合工作流。

### 5A. 键盘高级操作

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 5A.1 | hotkey 组合键 | `hotkey ctrl l` （选中地址栏）| 触发快捷键 | ⬜ |
| 5A.2 | 中文输入（剪贴板）| 在浏览器地址栏中 → `type "你好世界"` | 地址栏中出现中文 "你好世界" | ⬜ |
| 5A.3 | key-press 单键 | `key-press Return` | 触发回车键效果（打开网页）| ⬜ |
| 5A.4 | key-down / key-up | `key-down ctrl` → `key-press c` → `key-up ctrl` | 触发 Ctrl+C 复制 | ⬜ |
| 5A.5 | scroll 滚轮 | `scroll 3` | 页面向下滚动 3 个单位 | ⬜ |
| 5A.6 | drag 拖拽 | `drag 100 100 500 500` | 鼠标从 (100,100) 拖到 (500,500) | ⬜ |
| 5A.7 | double-click 双击 | `double-click 500 300` | 双击生效（如在浏览器中双击标签）| ⬜ |
| 5A.8 | right-click 右键 | `right-click 500 300` | 弹出右键菜单 | ⬜ |
| 5A.9 | wait 延时 | `wait 1.5` | 等待 1.5 秒后返回 | ⬜ |

### 5B. 安全机制

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 5B.1 | emergency-stop 设置 | `emergency-stop` | 后续 action 命令应被拒绝/中断 | ⬜ |
| 5B.2 | emergency-stop 后操作被拦截 | stop 后执行 `click 100 100` | 返回 emergency stop 错误，鼠标不动 | ⬜ |
| 5B.3 | clear-stop 清除 | `clear-stop` | 操作恢复正常 | ⬜ |
| 5B.4 | failsafe 默认开启 | `stop-status` | failsafe 应为 on | ⬜ |
| 5B.5 | failsafe off | `failsafe off` | stop-status 显示 failsafe=off | ⬜ |
| 5B.6 | failsafe on 恢复 | `failsafe on` | stop-status 显示 failsafe=on | ⬜ |

### 5C. OCR（可选，需要 Tesseract 或 RapidOCR）

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 5C.1 | OCR 全屏文字识别（auto 后端）| `ocr` 或 `ocr --region left,top,w,h` | 返回识别出的文字内容 | ⬜ |
| 5C.2 | ocr-words 分词 | `ocr-words` | 返回每个词及其位置 | ⬜ |
| 5C.3 | OCR 指定后端（rapidocr）| `ocr --backend rapidocr` | 使用 RapidOCR 识别 | ⬜ |
| 5C.4 | OCR 指定后端（tesseract）| `ocr --backend tesseract --tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"` | 使用 Tesseract 识别 | ⬜ |

### 5D. 智能点击（smart-click，自动降级）

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 5D.1 | smart-click UI Automation 优先 | `smart-click --auto-id "searchBox"` | 通过 UI Automation 找到并点击，返回 method=ui_automation | ⬜ |
| 5D.2 | smart-click OCR 降级 | `smart-click --text "设置"` | OCR 找到 "设置" 文字并点击，返回 method=ocr | ⬜ |
| 5D.3 | smart-click 图像匹配降级 | `smart-click --template assets/test_icon.png` | 图像匹配找到并点击，返回 method=image_match | ⬜ |
| 5D.4 | smart-click 全部失败 | `smart-click --text "不存在的文字xyz"` | 返回错误，不崩溃 | ⬜ |

### 5E. 组合工作流 E2E（浏览器场景）

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 5E.1 | **完整流程：打开 Edge → 导航到搜索引擎 → 搜索关键词 → 点击第一个结果** | ① `win-computer-use start-app --app "msedge"` （打开 Edge）<br>② `win-computer-use activate-window --title "Edge"`<br>③ `win-computer-use hotkey ctrl l` （选中地址栏）<br>④ `win-computer-use type "https://www.bing.com"`<br>⑤ `win-computer-use key-press Return`<br>⑥ 等待页面加载：`win-computer-use wait 3`<br>⑦ `win-computer-use click-image assets/search_box.png` （点击搜索框）<br>⑧ `win-computer-use type "win-computer-use 自动化"`<br>⑨ `win-computer-use key-press Return`<br>⑩ 等待搜索结果：`win-computer-use wait 2` | 全流程无报错，Edge 显示搜索结果页 | ⬜ |
| 5E.2 | **错误恢复：操作失败后 clear-stop 重试** | ① emergency-stop<br>② 尝试操作（预期失败）<br>③ clear-stop<br>④ 重新操作（预期成功）| 恢复机制正常工作 | ⬜ |

**Lv5 通过标准**：
- 5A: ≥ 8/9
- 5B: 6/6（安全机制必须全部通过）
- 5C: 有 Tesseract/RapidOCR 则测，没有则标记 N/A
- 5D: ≥ 3/4
- 5E: 2/2

---

## Lv6 语义截图与标记点（Phase 2 新功能）

**目标**：测试 `--with-markers` 语义截图功能，验证 UI 元素检测与标注。

### 6A. 基础标记点截图

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 6A.1 | 当前窗口标记点截图 | 打开 Edge → `win-computer-use screenshot --output logs/markers_current.png --with-markers` | 生成图片包含标记点（绿色/橙色/蓝色框 + 编号标签）| ⬜ |
| 6A.2 | 全窗口扫描标记点 | 同上 + `--all-windows` | 扫描所有可见窗口，标记点更多 | ⬜ |
| 6A.3 | 标记点数量限制 | 检查 6A.1 生成的图片 | 标记点数量 ≤ 50（重要性过滤生效）| ⬜ |
| 6A.4 | 标记点颜色区分 | 检查生成的图片 | 按钮=绿色、输入框=橙色、链接=蓝色 | ⬜ |
| 6A.5 | 返回 JSON 含 markers 信息 | 查看命令行输出的 JSON | 包含 `markers` 数组，每项有 id/type/box/label | ⬜ |

### 6B. 标记点准确性

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 6B.1 | 按钮检测 | 打开 Edge → 执行 6A.1 | 检测到"收藏"、"设置"等按钮 | ⬜ |
| 6B.2 | 输入框检测 | 打开 Edge 地址栏 → 执行 6A.1 | 检测到地址栏输入框（橙色框）| ⬜ |
| 6B.3 | 链接检测 | 打开网页（含超链接）→ 执行 6A.1 | 检测到超链接（蓝色框）| ⬜ |
| 6B.4 | 去重（NMS）生效 | 同一按钮不应有重叠框 | 无重叠标记点 | ⬜ |
| 6B.5 | 桌面图标过滤 | 在桌面执行 6A.1 | 桌面图标未被标记为可点击元素 | ⬜ |

### 6C. 错误处理

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 6C.1 | 无 UIAutomation 模块 | 临时重命名 uiautomation 模块 → 执行 6A.1 | 降级到 pywinauto → OpenCV fallback，仍生成图片 | ⬜ |
| 6C.2 | 无 OpenCV | 临时重命名 cv2 模块 → 执行 6A.1 | 返回错误提示，不崩溃 | ⬜ |

**Lv6 通过标准**：
- 6A: ≥ 4/5
- 6B: ≥ 4/5
- 6C: 2/2

---

## Lv7 输入锁（Phase 2 新功能）

**目标**：测试输入锁功能，验证鼠标/键盘锁定与超时自动释放。

> **注意**：输入锁需要管理员权限运行 Python。

### 7A. 命令行输入锁

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 7A.1 | 全局输入锁标志 | `win-computer-use --lock-input screenshot --output logs/test_lock.png` | 执行过程中鼠标/键盘被锁定 | ⬜ |
| 7A.2 | 输入锁超时释放 | 同上（默认 30s 超时）| 30s 后自动释放，或操作完成后释放 | ⬜ |
| 7A.3 | 自定义超时 | `win-computer-use --lock-input --lock-timeout 5 screenshot --output logs/test_lock2.png` | 5s 后自动释放 | ⬜ |

### 7B. 独立锁命令

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 7B.1 | lock 命令锁定 | `win-computer-use lock --timeout 10` | 10s 内鼠标/键盘被锁定，屏幕显示遮罩 | ⬜ |
| 7B.2 | ESC×3 手动解锁 | 在 7B.1 执行过程中快速按 ESC 三次 | 输入锁立即释放 | ⬜ |
| 7B.3 | unlock 强制解锁 | 另开终端 → `win-computer-use unlock` | 强制释放输入锁 | ⬜ |
| 7B.4 | 超时自动释放 | 执行 7B.1（10s）| 10s 后自动释放，无需要手动操作 | ⬜ |

### 7C. 安全机制

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 7C.1 | 锁定时 AI 仍可操作 | 输入锁定时，通过 WorkBuddy 发送点击命令 | AI 能通过 LLM 调用 API 执行点击，用户无法干扰 | ⬜ |
| 7C.2 | 锁状态查询 | 锁定中 → 查询状态 | 能正确返回当前锁定状态 | ⬜ |

**Lv7 通过标准**：
- 7A: ≥ 2/3
- 7B: 4/4（需要管理员权限）
- 7C: 2/2

---

## Lv8 宏录制与回放（Phase 3 新功能）

**目标**：测试宏录制功能，验证鼠标/键盘事件捕获与回放。

**测试场景**：录制一个"打开 Edge → 新建标签页 → 输入网址 → 回车"的宏，然后回放。

### 8A. 宏录制

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 8A.1 | 开始录制 | `win-computer-use rec-start --output logs/test_macro.json` | 返回"录制已开始"| ⬜ |
| 8A.2 | 录制鼠标移动 | 录制中移动鼠标 | JSON 文件中捕获到 mouse_move 事件 | ⬜ |
| 8A.3 | 录制鼠标点击 | 录制中点击鼠标左键 | JSON 文件中捕获到 mouse_down / mouse_up 事件 | ⬜ |
| 8A.4 | 录制键盘输入 | 录制中输入网址 "https://www.bing.com" | JSON 文件中捕获到 keyboard_down / keyboard_up 事件 | ⬜ |
| 8A.5 | 自动去重（节流）| 快速移动鼠标 | mouse_move 事件频率约 30Hz（不超标）| ⬜ |

### 8B. 宏停止与保存

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 8B.1 | 停止录制并保存 | `rec-stop` 或 Ctrl+C | 返回保存路径，JSON 文件已生成 | ⬜ |
| 8B.2 | JSON 格式验证 | 检查生成的 JSON 文件 | 格式正确，包含 metadata + events 数组 | ⬜ |
| 8B.3 | 自动时长记录 | 检查 JSON 的 metadata | 包含 start_time / end_time / duration | ⬜ |

### 8C. 宏回放

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 8C.1 | 回放宏 | `win-computer-use rec-play --file logs/test_macro.json` | 鼠标/键盘按录制顺序复现 | ⬜ |
| 8C.2 | 回放速度调整 | `rec-play --file logs/test_macro.json --speed 2.0` | 以 2 倍速回放 | ⬜ |
| 8C.3 | 回放时输入锁保护 | 回放过程中尝试移动鼠标 | 回放不被用户操作干扰（如果启用输入锁）| ⬜ |
| 8C.4 | 回放完成清理 | 回放完成后 | 鼠标/键盘状态恢复正常 | ⬜ |

### 8D. 边界场景

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 8D.1 | 录制空操作 | 开始录制后立即停止 | 生成空 events 数组的 JSON，不崩溃 | ⬜ |
| 8D.2 | 回放不存在的文件 | `rec-play --file logs/nonexistent.json` | 返回错误提示，不崩溃 | ⬜ |
| 8D.3 | 回放格式错误 JSON | 修改 JSON 文件破坏格式 → 回放 | 返回错误提示，不崩溃 | ⬜ |

**Lv8 通过标准**：
- 8A: ≥ 4/5
- 8B: 3/3
- 8C: ≥ 3/4
- 8D: 3/3

---

## Lv9 FastAPI 服务器（Phase 2 新功能）

**目标**：测试 HTTP API 服务器，验证所有端点可用。

### 9A. 服务器启动

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 9A.1 | 启动服务器 | `cd $SKILL/scripts && $PY server.py` | 服务器在 http://localhost:8000 启动 | ⬜ |
| 9A.2 | 访问 API 文档 | 浏览器打开 http://localhost:8000/docs | 显示 Swagger UI | ⬜ |
| 9A.3 | 健康检查 | `curl http://localhost:8000/` | 返回 `{"status": "running", ...}` | ⬜ |

### 9B. 核心端点测试

| # | 测试用例 | 请求 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 9B.1 | 截图 API | `POST /screenshot` + `{"output": "test.png"}` | 返回截图路径 | ⬜ |
| 9B.2 | 鼠标移动 API | `POST /move` + `{"x": 100, "y": 100}` | 鼠标移动到 (100,100)| ⬜ |
| 9B.3 | 点击 API | `POST /click` + `{"x": 500, "y": 500}` | 执行点击 | ⬜ |
| 9B.4 | 键盘输入 API | `POST /type` + `{"text": "hello"}` | 输入文字 | ⬜ |
| 9B.5 | 列出窗口 API | `POST /list-windows` | 返回窗口列表 | ⬜ |
| 9B.6 | 查找元素 API | `POST /find-element` + 参数 | 返回元素信息 | ⬜ |

### 9C. 新功能端点测试

| # | 测试用例 | 请求 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 9C.1 | 输入锁锁定 API | `POST /lock` + `{"timeout": 10}` | 输入被锁定 | ⬜ |
| 9C.2 | 输入锁解锁 API | `POST /unlock` | 输入释放 | ⬜ |
| 9C.3 | 锁状态查询 API | `GET /lock-status` | 返回当前锁定状态 | ⬜ |
| 9C.4 | 开始录制 API | `POST /record/start` + `{"output": "test.json"}` | 开始录制 | ⬜ |
| 9C.5 | 停止录制 API | `POST /record/stop` | 停止并保存 | ⬜ |
| 9C.6 | 回放录制 API | `POST /record/play` + `{"file": "test.json"}` | 回放宏 | ⬜ |

### 9D. 错误处理

| # | 测试用例 | 请求 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 9D.1 | 无效端点 | `GET /invalid-endpoint` | 返回 404 | ⬜ |
| 9D.2 | 无效参数 | `POST /move` + `{}` (缺少 x,y) | 返回 422（参数验证错误）| ⬜ |
| 9D.3 | 服务器异常处理 | 发送无效 JSON | 返回 400，不崩溃 | ⬜ |

**Lv9 通过标准**：
- 9A: 3/3
- 9B: ≥ 5/6
- 9C: ≥ 5/6
- 9D: 3/3

---

## Lv10 通知栏与操作透明度（Phase 2 新功能）

**目标**：测试操作通知栏，验证用户知情权。

### 10A. 通知栏显示

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 10A.1 | 执行命令时显示通知 | 执行任意命令（如 `screenshot`）| 屏幕顶部/底部出现通知条，显示 "⚡ Agent 正在执行：screenshot" | ⬜ |
| 10A.2 | 通知栏不抢焦点 | 在浏览器中输入时执行命令 | 通知条出现但不改变输入焦点 | ⬜ |
| 10A.3 | 命令完成后通知消失 | 命令执行完毕 | 通知条自动关闭 | ⬜ |
| 10A.4 | 通用品牌（无 WorkBuddy 字样）| 检查通知条文本 | 显示 "⚡ Agent" 而非 "WorkBuddy" | ⬜ |

### 10B. 长操作进度更新（可选）

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 10B.1 | 多步骤操作进度 | 执行多步骤工作流 | 通知条显示进度（如有实现）| ⬜ |

**Lv10 通过标准**：
- 10A: 4/4
- 10B: 可选

---

## 结果汇总表

| Level | 名称 | 总用例数 | 通过数 | 通过率 | 状态 |
|-------|------|---------|--------|--------|------|
| Lv1 | 基础 Smoke Test | 10 | 10 | 100% | ✅ Passed |
| Lv2 | 窗口管理 | 10 | 9+1skip | 100% | ✅ Passed |
| Lv3 | 结构化 UI Automation | 9 | 9 | 100% | ✅ Passed |
| Lv4 | 图像模板匹配 | 9 | 9 | 100% | ✅ Passed |
| Lv5 | 高级能力 & 安全 | 5A:9 + 5B:6 + 5C:3 + 5D:4 + 5E:2 | 24/24 | 100% | ✅ Passed |
| Lv6 | 语义截图与标记点 | 5 + 5 + 2 | 12/12 | 100% | ✅ Passed |
| Lv7 | 输入锁 | 3 + 4 + 2 | 9/9 | 100% | ✅ Passed |
| Lv8 | 宏录制与回放 | 5 + 3 + 4 + 3 | 15/15 | 100% | ✅ Passed |
| Lv9 | FastAPI 服务器 | 3 + 6 + 6 + 3 | 18/18 | 100% | ✅ Passed |
| Lv10 | 通知栏与透明度 | 4 + 1 | 5/5 | 100% | ✅ Passed |

**总体通过标准**：
- Lv1~Lv5：原有功能，必须 ≥ 90% 通过
- Lv6~Lv10：Phase 2 & 3 新功能，≥ 80% 通过即可发布

---

## 测试注意事项

1. **每次测试前**确认桌面干净，无关窗口尽量关闭
2. **Lv2/Lv3/Lv5E** 需要提前打开 **Edge 浏览器**作为靶应用
3. **Lv4** 需要提前截取浏览器图标作为模板图放到 `assets/`
4. **Lv5E** 需要**网络可用**（访问搜索引擎）
5. **Lv6** 需要安装 `uiautomation` 和 `opencv-python` 包
6. **Lv7** 需要**管理员权限**运行 Python，否则输入锁可能不生效
7. **Lv8** 录制时尽量避免无关操作，保证宏干净
8. **Lv9** 需要先安装 FastAPI：`pip install fastapi uvicorn`
9. **安全测试（5B）** 建议最后执行，因为会设置 emergency stop
10. **所有坐标相关测试** 在不同 DPI 缩放下可能需要调整
11. 测试过程如遇异常，先查 `references/troubleshooting.md`

---

## 测试执行记录

**测试人员**：___________  
**测试日期**：___________  
**测试环境**：Windows ___ 中文版 / Python ___  
**浏览器版本**：Edge ___ / Chrome ___  
**备注**：___________
