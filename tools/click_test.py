# -*- coding: utf-8 -*-
"""鼠标点击交互回归：点击分区执行并悬停、连点多次、点击中心关闭、圆外关闭。

运行会短暂接管键盘并移动鼠标，结束自动卸载钩子。
"""

import os
import sys
import time

os.environ["QUICKDIAL_ALLOW_INJECTED"] = "1"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import ctypes  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

from app import actions, config as cfgmod, native  # noqa: E402
from app.controller import Controller  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ALT, W, ESC = 0x12, 0x57, 0x1B
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
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


def _mouse(flags):
    inp = native.INPUT()
    inp.type = 0
    inp.mi = native.MOUSEINPUT(0, 0, 0, flags, 0, 0)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(native.INPUT))


def click(app, x, y, settle=320):
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    pump(app, 130)
    _mouse(MOUSEEVENTF_LEFTDOWN)
    pump(app, 45)
    _mouse(MOUSEEVENTF_LEFTUP)
    pump(app, settle)


def release_hotkey(app, wait=700):
    native._send_key(W, True)
    pump(app, 90)
    native._send_key(ALT, True)
    pump(app, wait)


def sector_pos(ctrl, index):
    import math

    cx, cy = ctrl.wheel.center_global()
    r = ctrl.wheel.radius()
    n = len(ctrl.wheel.wheel_config()["segments"])
    ang = math.radians(index * 360.0 / n)
    return cx + math.sin(ang) * r * 0.68, cy - math.cos(ang) * r * 0.68


def open_wheel(app, ctrl):
    native._send_key(ALT, False)
    pump(app, 70)
    native._send_key(W, False)
    pump(app, 420)
    if not ctrl.wheel.active:
        print("    [debug] armed=%s active=%s visible=%s closing=%s cfg=%s mods=%s"
              % (ctrl._armed, ctrl.wheel.active, ctrl.wheel.isVisible(),
                 ctrl.wheel._closing, ctrl.wheel.wheel_config() is not None,
                 native.modifier_state()))
    return ctrl.wheel.active


def main():
    app = QApplication(sys.argv)
    ctrl = Controller(app)
    cfg = cfgmod.default_config()
    cfg["wheels"][0]["hotkey"] = {"vk": W, "mods": ["alt"], "label": "Alt+W"}
    cfg["wheels"][0]["diameter"] = 380
    ctrl.cfg = cfg
    if not ctrl.start():
        print("钩子启动失败")
        return 1
    pump(app, 350)

    calls = []
    real_execute = actions.execute

    def fake_execute(action):
        calls.append(action)
        return True, ""

    actions.execute = fake_execute

    try:
        scr = app.primaryScreen().availableGeometry()
        ctypes.windll.user32.SetCursorPos(scr.x() + scr.width() // 2, scr.y() + scr.height() // 2)
        pump(app, 180)
        fg_before = ctypes.windll.user32.GetForegroundWindow()

        print("== 呼出 ==")
        check("转盘呼出", open_wheel(app, ctrl))
        check("呼出后前台窗口未改变（不抢焦点）",
              fg_before == ctypes.windll.user32.GetForegroundWindow())

        print("== 点击分区：执行 + 悬停 ==")
        x, y = sector_pos(ctrl, 0)
        click(app, x, y)
        release_hotkey(app)  # 点击时热键还按着，松手后动作才发出
        check("点击分区 0 执行 1 次", len(calls) == 1, len(calls))
        check("点击后转盘仍在显示（悬停）", ctrl.wheel.active)
        check("进入悬停锁定状态", ctrl.wheel.click_locked)

        print("== 连点不同分区 ==")
        x, y = sector_pos(ctrl, 2)
        click(app, x, y)
        pump(app, 200)
        check("点击分区 2 再执行一次", len(calls) == 2, len(calls))
        x, y = sector_pos(ctrl, 4)
        click(app, x, y)
        pump(app, 200)
        check("点击分区 4 第三次执行", len(calls) == 3, len(calls))
        check("执行的是对应分区的动作",
              calls[-1] == ctrl.wheel.wheel_config()["segments"][4]["action"], calls[-1])
        check("连点后仍然悬停", ctrl.wheel.active and ctrl.wheel.click_locked)

        print("== 点击中心关闭 ==")
        cx, cy = ctrl.wheel.center_global()
        click(app, cx, cy, settle=520)
        check("点击中心后关闭", not ctrl.wheel.active)
        check("点击中心不执行动作", len(calls) == 3, len(calls))

        print("== 点击转盘空白区域关闭 ==")
        check("再次呼出", open_wheel(app, ctrl))
        cx, cy = ctrl.wheel.center_global()
        r = ctrl.wheel.radius()
        click(app, cx + r * 1.2, cy, settle=520)  # 圆外、窗口内的透明区域
        check("点击转盘外关闭", not ctrl.wheel.active)
        check("点击圆外不执行动作", len(calls) == 3, len(calls))

        print("== 不点击时仍是松手执行 ==")
        calls.clear()
        check("再次呼出", open_wheel(app, ctrl))
        x, y = sector_pos(ctrl, 1)
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        pump(app, 220)  # 只悬停不点击
        release_hotkey(app, wait=900)
        check("松手执行选中分区", len(calls) == 1, len(calls))
        check("松手后转盘关闭", not ctrl.wheel.active)

        print("== Esc 仍可取消 ==")
        calls.clear()
        check("再次呼出", open_wheel(app, ctrl))
        native._send_key(ESC, False)
        pump(app, 120)
        native._send_key(ESC, True)
        pump(app, 320)
        native._send_key(W, True)
        pump(app, 100)
        native._send_key(ALT, True)
        pump(app, 700)
        check("Esc 关闭且不执行", not ctrl.wheel.active and len(calls) == 0, len(calls))

        print("== 悬停中按 Esc 也能关闭 ==")
        calls.clear()
        check("再次呼出", open_wheel(app, ctrl))
        x, y = sector_pos(ctrl, 3)
        click(app, x, y)
        release_hotkey(app)
        check("点击后处于悬停", ctrl.wheel.active and ctrl.wheel.click_locked)
        native._send_key(ESC, False)
        pump(app, 120)
        native._send_key(ESC, True)
        pump(app, 600)
        check("悬停中 Esc 关闭", not ctrl.wheel.active)
    finally:
        actions.execute = real_execute
        ctrl.shutdown()
        ctrl.wheel.finish_close()

    print("\n" + "=" * 44)
    print("通过 %d 项，失败 %d 项" % (PASS, FAIL))
    print("=" * 44)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
