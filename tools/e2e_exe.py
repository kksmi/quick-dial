# -*- coding: utf-8 -*-
"""验证打包后的 EXE：启动 → 注入 Alt+W → 抓取光标附近画面 → 结束。

只做端到端冒烟，抓图区域限制在转盘附近，避免截取无关窗口内容。
"""

import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.environ["QUICKDIAL_ALLOW_INJECTED"] = "1"

import ctypes  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

from app import native  # noqa: E402

EXE = os.path.join(ROOT, "dist", "快捷转盘.exe")


def pump(app, sec):
    end = time.time() + sec
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main():
    if not os.path.exists(EXE):
        print("未找到 EXE:", EXE)
        return 1

    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    geo = screen.geometry()
    print("屏幕:", geo.width(), "x", geo.height())

    env = dict(os.environ)
    env["QUICKDIAL_ALLOW_INJECTED"] = "1"
    proc = subprocess.Popen([EXE], env=env)
    print("启动 PID", proc.pid)
    pump(app, 9)

    if proc.poll() is not None:
        print("FAIL: 进程启动后已退出，code =", proc.returncode)
        return 1
    print("进程存活 OK")

    # 光标放到右下空白处，减少与设置窗口重叠
    tx, ty = geo.width() - 320, geo.height() - 300
    ctypes.windll.user32.SetCursorPos(tx, ty)
    pump(app, 0.4)

    native._send_key(0x12, False)  # Alt
    pump(app, 0.1)
    native._send_key(0x57, False)  # W
    print("已注入 Alt+W，等待呼出")
    pump(app, 1.1)

    shot = screen.grabWindow(0, tx - 320, ty - 320, 640, 640)
    out = os.path.join(ROOT, "assets", "exe_live.png")
    shot.save(out)
    print("截图:", out)

    # 选中：把光标往上移，然后松开执行（默认第 0 块 Ctrl+C，无破坏性）
    ctypes.windll.user32.SetCursorPos(tx, ty - 150)
    pump(app, 0.5)
    native._send_key(0x57, True)
    pump(app, 0.1)
    native._send_key(0x12, True)
    pump(app, 1.2)

    proc.terminate()
    try:
        proc.wait(6)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("已退出，code =", proc.returncode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
