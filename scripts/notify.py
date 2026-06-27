"""
notify.py - 操作通知提示条

在屏幕顶部显示一个轻量级提示条，告知用户 AI 正在操作电脑。
使用 Tkinter（Python 自带），无额外依赖。

用法：
    from notify import NotifyBar
    bar = NotifyBar()
    bar.show("正在打开浏览器...")
    bar.update_progress(1, 5)
    # ... 执行操作 ...
    bar.close()
"""

import tkinter as tk
from tkinter import font
import threading
import time

# Windows 系统参数
BAR_HEIGHT = 36          # 提示条高度
BG_COLOR = "#1a1a2e"   # 深色背景
FG_COLOR = "#e94560"     # 强调色（红）
TEXT_COLOR = "#ffffff"    # 文字颜色
FONT_FAMILY = "Microsoft YaHei UI"  # Windows 中文字体


class NotifyBar:
    """
    屏幕顶部操作通知条。

    特性：
    - 始终置顶（topmost）
    - 不抢焦点（toolwindow + 特殊窗口样式）
    - 显示操作描述和进度
    - 自动消失（超时或手动关闭）
    """

    def __init__(self):
        self.root = None
        self._thread = None
        self._label_text = None
        self._label_progress = None
        self._canvas = None
        self._progress_width = 0
        self._total_steps = 0
        self._current_step = 0

    def show(self, message: str = "⚡ Agent 正在操作电脑，请勿干扰", total_steps: int = 0):
        """
        显示提示条。

        :param message: 提示信息
        :param total_steps: 总步骤数（0 表示不显示进度）
        """
        self._total_steps = total_steps
        self._current_step = 0

        def _run():
            self.root = tk.Tk()
            self.root.overrideredirect(True)   # 无边框
            self.root.wm_attributes("-topmost", True)
            self.root.wm_attributes("-toolwindow", True)  # 不在任务栏显示
            self.root.configure(bg=BG_COLOR)

            # 计算屏幕宽度，提示条横跨整个屏幕顶部
            screen_width = self.root.winfo_screenwidth()
            self.root.geometry(f"{screen_width}x{BAR_HEIGHT}+0+0")

            # 主容器
            frame = tk.Frame(self.root, bg=BG_COLOR, height=BAR_HEIGHT)
            frame.pack(fill="x")
            frame.pack_propagate(False)

            # 图标 + 文字
            self._label_text = tk.Label(
                frame,
                text=message,
                bg=BG_COLOR,
                fg=TEXT_COLOR,
                font=(FONT_FAMILY, 10, "bold"),
                anchor="w",
                padx=16,
            )
            self._label_text.pack(side="left", fill="x", expand=True)

            # 进度标签（右侧）
            if total_steps > 0:
                self._label_progress = tk.Label(
                    frame,
                    text=f"[ 0 / {total_steps} ]",
                    bg=BG_COLOR,
                    fg=FG_COLOR,
                    font=(FONT_FAMILY, 9),
                    anchor="e",
                    padx=16,
                )
                self._label_progress.pack(side="right")

            # 底部进度条（canvas 绘制）
            if total_steps > 0:
                self._canvas = tk.Canvas(
                    frame,
                    height=3,
                    bg=BG_COLOR,
                    highlightthickness=0,
                )
                self._canvas.pack(side="bottom", fill="x")
                self._progress_width = screen_width

            # 点击提示条可手动关闭（紧急停止）
            frame.bind("<Button-1>", lambda e: self.close())
            self._label_text.bind("<Button-1>", lambda e: self.close())

            self.root.mainloop()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        time.sleep(0.1)  # 等待 UI 线程启动

    def update_message(self, message: str):
        """更新提示文字。"""
        if self._label_text and self.root:
            self.root.after(0, lambda: self._label_text.config(text=message))

    def update_progress(self, current: int, total: int = None):
        """
        更新进度。

        :param current: 当前步骤（从 1 开始）
        :param total: 总步骤数（可选，不传则用之前设置的）
        """
        if total is not None:
            self._total_steps = total
        self._current_step = current

        if self._label_progress and self.root:
            self.root.after(
                0,
                lambda: self._label_progress.config(
                    text=f"[ {current} / {self._total_steps} ]"
                ),
            )

        # 更新底部进度条
        if self._canvas and self._total_steps > 0:
            ratio = min(current / self._total_steps, 1.0)
            bar_w = int(self._progress_width * ratio)
            self.root.after(
                0,
                lambda: self._canvas.delete("all")
                or self._canvas.create_rectangle(
                    0, 0, bar_w, 3, fill=FG_COLOR, width=0
                ),
            )

    def pulse(self):
        """
        显示"正在处理..."的脉冲动画（用于不确定进度的场景）。
        在提示文字后加省略号动画。
        """
        if self._label_text and self.root:
            base = self._label_text.cget("text").rstrip(".")
            dots = "." * (((int(time.time()) % 3) + 1))
            self.root.after(0, lambda: self._label_text.config(text=base + dots))

    def close(self):
        """关闭提示条。"""
        if self.root:
            try:
                self.root.after(0, self.root.destroy)
            except Exception:
                pass
            self.root = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# --------------------------------------------------
# CLI 快捷入口（供 cli.py 调用）
# --------------------------------------------------

def notify_context(message: str = "⚡ Agent 正在操作电脑，请勿干扰", total_steps: int = 0):
    """
    返回一个 context manager，用于 with 语句：

        with notify_context("正在操作...", total_steps=5) as bar:
            bar.update_progress(1, 5)
            # ... 执行操作 ...
        # 自动关闭

    如果 total_steps=0，不显示进度条。
    """
    bar = NotifyBar()
    bar.show(message, total_steps)
    return bar


if __name__ == "__main__":
    # 测试：显示 5 秒，模拟进度更新
    import time

    bar = NotifyBar()
    bar.show("⚡ Agent 正在操作电脑，请勿干扰", total_steps=5)
    time.sleep(1)

    for i in range(1, 6):
        bar.update_message(f"正在执行步骤 {i}...")
        bar.update_progress(i)
        time.sleep(1)

    bar.update_message("✅ 操作完成")
    time.sleep(1.5)
    bar.close()
    print("测试完成")
