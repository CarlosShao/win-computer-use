# workbuddy-computer-use 测试方案（Lv1 → Lv5）

> 本文档为 `workbuddy-computer-use` 技能的分级测试方案。
> 每个等级独立可执行，按顺序递进。在新会话中逐级测试，记录结果。

---

## 环境准备

```bash
# 确认 Python 路径
PY="C:/Users/swq/.workbuddy/binaries/python/envs/computer-use/Scripts/python.exe"
SKILL="D:/work/java/AI-workspace/skills/.workbuddy/skills/workbuddy-computer-use"

# 快捷命令（每次测试前确认可用）
"$PY" "$SKILL/scripts/cli.py" --help
```

**前置条件：**
- [ ] Python venv 已创建且依赖已安装 (`pip install -r scripts/requirements.txt`)
- [ ] 显示器分辨率已知（当前 3440x1440）
- [ ] 测试用目标应用已安装：记事本 (Notepad)、计算器 (Calculator)
- [ ] Tesseract OCR 已安装（Lv5 需要，没有则跳过 OCR 用例）

---

## Lv1 基础能力验证（Smoke Test）

**目标**：确认 CLI 能正常启动、截图、获取屏幕信息、鼠标键盘基本操作。

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 1.1 | CLI `--help` 正常输出 | `$PY $SKILL/scripts/cli.py --help` | 输出所有子命令列表，无报错 | ⬜ |
| 1.2 | 全屏截图 | `$PY $SKILL/scripts/cli.py screenshot --output logs/test_lv1.png` | 返回 JSON 含 path/width/height，文件存在 | ⬜ |
| 1.3 | 截图带 base64 | `同上 + --base64` | JSON 中含 base64 字段，长度 > 0 | ⬜ |
| 1.4 | 获取屏幕尺寸 | `$PY $SKILL/scripts/cli.py screen-size` | 返回 `{width, height}` 匹配实际分辨率 | ⬜ |
| 1.5 | 获取鼠标位置 | `$PY $SKILL/scripts/cli.py mouse-position` | 返回 `{x, y}` 在屏幕范围内 | ⬜ |
| 1.6 | 鼠标移动 | `$PY $SKILL/scripts/cli.py move 100 100` → 再 mouse-position | 鼠标在 (100,100) 位置（允许 ±2px 误差） | ⬜ |
| 1.7 | 单击 | `$PY $SKILL/scripts/cli.py click 500 500` | 执行无报错 | ⬜ |
| 1.8 | 键盘输入英文 | `$PY $SKILL/scripts/cli.py type "hello_world"` | 执行无报错（建议在记事本中验证） | ⬜ |
| 1.9 | 安全状态查询 | `$PY $SKILL/scripts/cli.py stop-status` | 返回 emergency_stop / failsafe 状态 | ⬜ |

**Lv1 通过标准**：全部 9 项通过 ✅

---

## Lv2 窗口管理

**目标**：能发现、激活、操控窗口。

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 2.1 | 列出所有窗口 | `$PY $SKILL/scripts/cli.py list-windows` | 返回 JSON 数组，每项含 title/handle/pid/rect | ⬜ |
| 2.2 | 过滤窗口 | `$PY $SKILL/scripts/cli.py list-windows --filter "Notepad"` | 只返回匹配的窗口 | ⬜ |
| 2.3 | 查找窗口 | `$PY $SKILL/scripts/cli.py find-window --title "Notepad"` | 返回窗口信息或明确的 "not found" | ⬜ |
| 2.4 | 激活窗口 | 先打开记事本 → `activate-window --title "Untitled - Notepad"` | 记事本窗口置顶获得焦点 | ⬜ |
| 2.5 | 最小化窗口 | `minimize --title "Untitled - Notepad"` | 窗口最小化到任务栏 | ⬜ |
| 2.6 | 最大化窗口 | `maximize --title "Untitled - Notepad"` | 窗口全屏最大化 | ⬜ |
| 2.7 | 恢复窗口 | `restore --title "Untitled - Notepad"` | 窗口恢复之前大小 | ⬜ |
| 2.8 | 获取窗口矩形 | `window-rect --title "Untitled - Notepad"` | 返回 {left, top, right, bottom} | ⬜ |
| 2.9 | 关闭窗口（⚠️ 会关闭应用） | `close-window --title "Untitled - Notepad"` | 窗口关闭 | ⬜ |

**Lv2 通过标准**：≥ 8/9 通过（close-window 可选跳过避免误操作）✅

---

## Lv3 结构化 UI Automation

**目标**：通过 UI Automation 控件树查找并操作元素（pywinauto）。

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 3.1 | 打开「保存对话框」触发 | 在记事本中 Ctrl+S 打开 Save As 对话框 | 对话框出现 | ⬜ |
| 3.2 | find-element 按 name 查找 | `find-element --title "Save As" --control_type Button --name "Save"` | 返回控件信息（bounds 等） | ⬜ |
| 3.3 | find-element 按 auto_id 查找 | `find-element --title "Save As" --control_type Edit --auto_id "FileNameControl"` | 找到文件名输入框 | ⬜ |
| 3.4 | click-element 点击按钮 | `click-element --title "Save As" --control_type Button --name "Cancel"` | 对话框关闭（点了取消） | ⬜ |
| 3.5 | set-text 输入文本 | 重新打开 Save As → `set-text --title "Save As" --control_type Edit --auto_id "FileNameControl" --value "test_lv3.txt"` | 文件名填入 "test_lv3.txt" | ⬜ |
| 3.6 | element-text 读取控件文本 | `element-text --title "Save As" --control_type Edit --auto_id "FileNameControl"` | 返回 "test_lv3.txt" | ⬜ |
| 3.7 | wait-element 等待元素出现 | 关闭对话框后重新 Ctrl+S → `wait-element --title "Save As" --control_type Button --name "Save" --timeout 5` | 5 秒内返回成功 | ⬜ |
| 3.8 | 控件不存在时的错误处理 | `find-element --title "NotExistWindow" --control_type Button --name "Ok"` | 返回 `{ok: false, error: ...}` 不崩溃 | ⬜ |

**Lv3 通过标准**：≥ 7/8 通过 ✅

---

## Lv4 图像模板匹配

**目标**：OpenCV findImage/clickImage 能准确定位屏幕上的图标/按钮。

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 4.1 | 准备模板图片 | 截取一个小图标（如记事本菜单栏的 File），保存到 `assets/test_icon.png` | 模板文件存在，尺寸合理 (< 200x200) | ⬜ |
| 4.2 | find-image 基础匹配 | `find-image assets/test_icon.png` | 返回坐标和 confidence ≥ 0.82 | ⬜ |
| 4.3 | find-image 指定阈值 | `find-image assets/test_icon.png --threshold 0.90` | 高阈值下仍能找到（或明确返回未找到） | ⬜ |
| 4.4 | click-image 点击 | `click-image assets/test_icon.png` | 鼠标移动到目标位置并点击 | ⬜ |
| 4.5 | wait-image 等待图像出现 | `wait-image assets/test_icon.png --timeout 10` | 10 秒内返回成功 | ⬜ |
| 4.6 | count-image 统计匹配数 | `count-image assets/test_icon.png --threshold 0.85` | 返回正确的匹配数量 | ⬜ |
| 4.7 | 多匹配场景（NMS） | 屏幕上有多个相似图标时 locate_all | 返回去重后的正确数量（NMS 生效） | ⬜ |
| 4.8 | 无匹配时优雅降级 | `find-image assets/nonexistent.png` | 返回 `{ok: false}` 不崩溃不抛异常 | ⬜ |

**Lv4 通过标准**：≥ 7/8 通过 ✅

---

## Lv5 高级能力 & 安全机制

**目标**：OCR（可选）、安全停止、边界场景、中文输入、组合工作流。

### 5A. 键盘高级操作

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 5A.1 | hotkey 组合键 | `hotkey ctrl s` | 触发保存快捷键 | ⬜ |
| 5A.2 | 中文输入（剪贴板） | 在记事本中 → `type "你好世界"` | 记事本中出现中文 "你好世界" | ⬜ |
| 5A.3 | key-press 单键 | `key-press Return` | 触发回车键效果 | ⬜ |
| 5A.4 | scroll 滚轮 | `scroll 3` | 页面向下滚动 3 个单位 | ⬜ |
| 5A.5 | drag 拖拽 | `drag 100 100 500 500` | 鼠标从 (100,100) 拖到 (500,500) | ⬜ |
| 5A.6 | double-click 双击 | `double-click 500 300` | 双击生效（如在文件资源管理器中双击文件夹） | ⬜ |
| 5A.7 | right-click 右键 | `right-click 500 300` | 弹出右键菜单 | ⬜ |

### 5B. 安全机制

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 5B.1 | emergency-stop 设置 | `emergency-stop` | 后续 action 命令应被拒绝/中断 | ⬜ |
| 5B.2 | emergency-stop 后操作被拦截 | stop 后执行 `click 100 100` | 返回 emergency stop 错误，鼠标不动 | ⬜ |
| 5B.3 | clear-stop 清除 | `clear-stop` | 操作恢复正常 | ⬜ |
| 5B.4 | failsafe 默认开启 | `stop-status` | failsafe 应为 on | ⬜ |
| 5B.5 | failsafe off | `failsafe off` | stop-status 显示 failsafe=off | ⬜ |
| 5B.6 | failsafe on 恢复 | `failsafe on` | stop-status 显示 failsafe=on | ⬜ |

### 5C. OCR（可选，需要 Tesseract）

| # | 测试用例 | 命令 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 5C.1 | OCR 全屏文字识别 | `ocr` 或 `ocr --region left,top,w,h` | 返回识别出的文字内容 | ⬜ |
| 5C.2 | ocr-words 分词 | `ocr-words` | 返回每个词及其位置 | ⬜ |

### 5D. 组合工作流 E2E

| # | 测试用例 | 步骤 | 预期结果 | 通过? |
|---|---------|------|---------|-------|
| 5D.1 | 完整流程：打开记事本→输入→保存→关闭 | ① list-windows 找记事本<br>② activate-window 激活<br>③ type "E2E Test"<br>④ hotkey ctrl s<br>⑤ set-text 填文件名<br>⑥ click-element 点 Save<br>⑦ close-window | 全流程无报错，文件已保存 | ⬜ |
| 5D.2 | 错误恢复：操作失败后 clear-stop 重试 | ① emergency-stop<br>② 尝试操作（预期失败）<br>③ clear-stop<br>④ 重新操作（预期成功） | 恢复机制正常工作 | ⬜ |

**Lv5 通过标准**：
- 5A: ≥ 6/7
- 5B: 6/6（安全机制必须全部通过）
- 5C: 有 Tesseract 则测，没有则标记 N/A
- 5D: 2/2

---

## 结果汇总表

| Level | 名称 | 总用例数 | 通过数 | 通过率 | 状态 |
|-------|------|---------|--------|--------|------|
| Lv1 | 基础 Smoke Test | 9 | | | ⬜ Pending |
| Lv2 | 窗口管理 | 9 | | | ⬜ Pending |
| Lv3 | 结构化 UI Automation | 8 | | | ⬜ Pending |
| Lv4 | 图像模板匹配 | 8 | | | ⬜ Pending |
| Lv5 | 高级能力 & 安全 | 21+ | | | ⬜ Pending |

---

## 测试注意事项

1. **每次测试前**确认桌面干净，无关窗口尽量关闭
2. **Lv2/Lv3/L5D** 需要提前打开记事本作为靶应用
3. **Lv4** 需要提前截取模板图放到 `assets/`
4. **安全测试（5B）** 建议最后执行，因为会设置 emergency stop
5. **所有坐标相关测试** 在不同 DPI 缩放下可能需要调整
6. 测试过程如遇异常，先查 `references/troubleshooting.md`
