# -*- coding: utf-8 -*-
"""按键状态回归测试：验证松开热键后不会残留按键状态，且动作发出时修饰键已释放。

覆盖：
A. 正常按住 -> 选中 -> 先松主键再松 Alt
B. 快速点按（20ms）
C. 先松 Alt 再松主键
D. 先松 Shift 再松主键（多修饰键热键 Ctrl+Shift+F9）
"""

import os
import sys
import time

# 统一 UTF-8 输出：Windows 默认控制台编码可能是 cp1252/gbk，打印中文会直接抛异常
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

os.environ["QUICKDIAL_ALLOW_INJECTED"] = "1"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import ctypes  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

from app import actions, config as cfgmod, native  # noqa: E402
from app.controller import Controller  # noqa: E402

ALT, W, ESC, CTRL, SHIFT, F9 = 0x12, 0x57, 0x1B, 0x11, 0x10, 0x78
PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] %s" % name)
    else:
        FAIL += 1
        print("  [FAIL] %s  %s" % (name, detail))


def pump(app, ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def phys_any(vk):
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def move_to_sector(app, ctrl, index=0):
    """把光标移到某个扇区上，确保有选中项。"""
    cx, cy = ctrl.wheel.center_global()
    r = ctrl.wheel.radius()
    import math

    n = len(ctrl.wheel.wheel_config()["segments"])
    ang = math.radians(index * 360.0 / n)
    ctypes.windll.user32.SetCursorPos(int(cx + math.sin(ang) * r * 0.7), int(cy - math.cos(ang) * r * 0.7))
    pump(app, 180)


def run(app, ctrl, calls, name, hold_ms, release_first):
    """release_first: 'main' 先松主键 / 'mod' 先松修饰键"""
    calls.clear()
    print("\n--- %s ---" % name)
    # 每轮从屏幕中心开始，避免光标被边界 clamp 后与圆心重合
    scr = QApplication.primaryScreen().availableGeometry()
    ctypes.windll.user32.SetCursorPos(scr.x() + scr.width() // 2, scr.y() + scr.height() // 2)
    pump(app, 120)
    native._send_key(ALT, False)
    pump(app, 70)
    native._send_key(W, False)
    pump(app, max(60, hold_ms))
    opened = ctrl.wheel.active
    if opened:
        move_to_sector(app, ctrl, 0)

    if release_first == "main":
        native._send_key(W, True)
        pump(app, 120)
        native._send_key(ALT, True)
    else:
        native._send_key(ALT, True)
        pump(app, 120)
        native._send_key(W, True)

    pump(app, 1400)
    still_open = ctrl.wheel.active
    alt_stuck, w_stuck = phys_any(ALT), phys_any(W)

    check("%s：转盘打开" % name, opened)
    check("%s：转盘已关闭" % name, not still_open)
    check("%s：执行了 1 次动作" % name, len(calls) == 1, len(calls))
    check("%s：无按键残留 (alt=%s w=%s)" % (name, alt_stuck, w_stuck), not alt_stuck and not w_stuck)
    if calls:
        mods = calls[0][1]
        check("%s：动作发出时修饰键已释放 %s" % (name, mods), mods == (False, False, False, False))


def main():
    app = QApplication(sys.argv)
    ctrl = Controller(app)
    cfg = cfgmod.default_config()
    cfg["wheels"][0]["hotkey"] = {"vk": W, "mods": ["alt"], "label": "Alt+W"}
    ctrl.cfg = cfg
    if not ctrl.start():
        print("钩子启动失败")
        return 1
    pump(app, 300)

    calls = []

    def fake_execute(action):
        # 记录动作发出瞬间的修饰键状态，这是"分区快捷键是否被污染"的直接证据
        calls.append((action, native.modifier_state()))
        return True, ""

    real = actions.execute
    actions.execute = fake_execute
    try:
        run(app, ctrl, calls, "A 正常按住 400ms 先松主键", 400, "main")
        run(app, ctrl, calls, "B 快速点按 20ms", 20, "main")
        run(app, ctrl, calls, "C 先松 Alt 再松主键", 400, "mod")

        # D：多修饰键热键，先松 Shift
        print("\n--- D Ctrl+Shift+F9 先松 Shift ---")
        cfg["wheels"][0]["hotkey"] = {"vk": F9, "mods": ["ctrl", "shift"], "label": "Ctrl+Shift+F9"}
        ctrl.cfg = cfg
        calls.clear()
        scr = QApplication.primaryScreen().availableGeometry()
        ctypes.windll.user32.SetCursorPos(scr.x() + scr.width() // 2, scr.y() + scr.height() // 2)
        pump(app, 120)
        native._send_key(CTRL, False)
        pump(app, 60)
        native._send_key(SHIFT, False)
        pump(app, 60)
        native._send_key(F9, False)
        pump(app, 350)
        opened = ctrl.wheel.active
        if opened:
            move_to_sector(app, ctrl, 0)
        native._send_key(SHIFT, True)
        pump(app, 120)
        native._send_key(CTRL, True)
        pump(app, 120)
        native._send_key(F9, True)
        pump(app, 1400)
        check("D：转盘打开", opened)
        check("D：转盘已关闭", not ctrl.wheel.active)
        check("D：执行 1 次", len(calls) == 1, len(calls))
        check("D：无按键残留 (ctrl=%s shift=%s f9=%s)"
              % (phys_any(CTRL), phys_any(SHIFT), phys_any(F9)),
              not phys_any(CTRL) and not phys_any(SHIFT) and not phys_any(F9))
        if calls:
            check("D：动作发出时修饰键已释放 %s" % (calls[0][1],), calls[0][1] == (False, False, False, False))

        # E：Esc 取消后不应残留
        print("\n--- E Esc 取消 ---")
        calls.clear()
        native._send_key(CTRL, False)
        pump(app, 60)
        native._send_key(SHIFT, False)
        pump(app, 60)
        native._send_key(F9, False)
        pump(app, 350)
        native._send_key(ESC, False)
        pump(app, 100)
        native._send_key(ESC, True)
        pump(app, 300)
        native._send_key(SHIFT, True)
        pump(app, 100)
        native._send_key(CTRL, True)
        pump(app, 100)
        native._send_key(F9, True)
        pump(app, 600)
        check("E：Esc 后未执行动作", len(calls) == 0, len(calls))
        check("E：Esc 后无按键残留", not phys_any(CTRL) and not phys_any(SHIFT) and not phys_any(F9))
        check("E：转盘已关闭", not ctrl.wheel.active)
    finally:
        actions.execute = real
        ctrl.shutdown()
        ctrl.wheel.finish_close()

    print("\n" + "=" * 44)
    print("通过 %d 项，失败 %d 项" % (PASS, FAIL))
    print("=" * 44)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
