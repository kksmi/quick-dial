# -*- coding: utf-8 -*-
"""端到端验证：真实安装全局钩子，模拟按下热键 → 呼出 → 光标选中 → 松开执行。

运行前会短暂接管键盘（最多数秒），测试结束自动卸载钩子。
用 QUICKDIAL_ALLOW_INJECTED=1 让钩子接受 SendInput 注入的按键。
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

PASS, FAIL = 0, 0
LOGS = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] %s" % name)
    else:
        FAIL += 1
        print("  [FAIL] %s  %s" % (name, detail))


def wait(app, ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.008)


def key_down(vk):
    native._send_key(vk, False)


def key_up(vk):
    native._send_key(vk, True)


def wheel_event(delta):
    """注入鼠标滚轮。"""
    inp = native.INPUT()
    inp.type = 0
    inp.mi = native.MOUSEINPUT(0, 0, delta & 0xFFFFFFFF, 0x0800, 0, 0)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(native.INPUT))


def main():
    app = QApplication(sys.argv)
    calls = []
    real_execute = actions.execute
    actions.execute = lambda action: (calls.append(action), (True, ""))[1]

    ctrl = Controller(app)
    test_cfg = cfgmod.default_config()
    test_cfg["wheels"][0]["diameter"] = 380
    test_cfg["wheels"][0]["hotkey"] = {"vk": 0x57, "mods": ["alt"], "label": "Alt+W"}
    ctrl.cfg = test_cfg

    print("== 启动钩子 ==")
    ok = ctrl.start()
    check("钩子启动", ok)
    if not ok:
        return 1
    wait(app, 200)

    try:
        # ---------- 1. 呼叫前后光标不移动
        before = native.get_cursor_pos()
        print("== 按下 Alt+W ==")
        key_down(0x12)
        wait(app, 60)
        key_down(0x57)
        wait(app, 320)
        after = native.get_cursor_pos()
        check("热键呼出转盘", ctrl.wheel.isVisible() and ctrl.wheel.active, ctrl.wheel.isVisible())
        # 容差 6px：真实桌面上鼠标/触摸板本身会有微小漂移，本程序从不调用 SetCursorPos
        drift = max(abs(before[0] - after[0]), abs(before[1] - after[1]))
        check("呼出时光标不移动", drift <= 6, "%s -> %s" % (before, after))

        cx, cy = ctrl.wheel.center_global()
        r = ctrl.wheel.radius()
        print("    圆心=(%.0f,%.0f) 半径=%.0f 光标=%s" % (cx, cy, r, after))

        # ---------- 2. 跟随光标：圆心应落在光标附近
        check("跟随光标定位", abs(cx - after[0]) <= 6 and abs(cy - after[1]) <= 6,
              "center=%s cursor=%s" % ((cx, cy), after))

        # ---------- 3. 鼠标方向选中
        ctrl.wheel._index = -1
        ctypes.windll.user32.SetCursorPos(int(cx), int(cy - r * 0.75))
        wait(app, 160)
        check("上方 -> 第 0 块", ctrl.wheel.index == 0, ctrl.wheel.index)

        ctypes.windll.user32.SetCursorPos(int(cx + r * 0.75), int(cy))
        wait(app, 200)
        check("右侧 -> 第 2 块", ctrl.wheel.index == 2, ctrl.wheel.index)

        ctypes.windll.user32.SetCursorPos(int(cx), int(cy + r * 0.75))
        wait(app, 200)
        check("下方 -> 第 4 块", ctrl.wheel.index == 4, ctrl.wheel.index)

        # 截一张真实窗口的图（仅窗口内容）
        img = ctrl.wheel.grab().toImage()
        shot = os.path.join(os.path.dirname(__file__), "..", "assets", "e2e_wheel.png")
        img.save(shot)
        check("运行中转盘可截图", os.path.exists(shot))

        # ---------- 4. 松开热键 -> 执行第 4 块
        print("== 松开 Alt+W ==")
        key_up(0x57)
        wait(app, 80)
        key_up(0x12)
        wait(app, 1200)  # 等修饰键释放检测 + 动作执行
        check("转盘已关闭", not ctrl.wheel.active, ctrl.wheel.active)
        check("动作被执行一次", len(calls) == 1, calls)
        if calls:
            expect = test_cfg["wheels"][0]["segments"][4]["action"]
            check("执行的是选中的那块", calls[0] == expect, "%s vs %s" % (calls[0], expect))

        # ---------- 5. Esc 取消
        calls.clear()
        key_down(0x12)
        wait(app, 60)
        key_down(0x57)
        wait(app, 300)
        check("再次呼出", ctrl.wheel.active)
        key_down(0x1B)  # Esc
        wait(app, 120)
        key_up(0x1B)
        wait(app, 400)
        key_up(0x57)
        wait(app, 600)
        key_up(0x12)
        wait(app, 300)
        check("Esc 后不执行动作", len(calls) == 0, calls)
        check("Esc 后转盘关闭", not ctrl.wheel.active)

        # ---------- 6. 滚轮模式
        print("== 滚轮模式 ==")
        wheel_cfg = ctrl.cfg["wheels"][0]
        wheel_cfg["select_mode"] = cfgmod.SELECT_WHEEL
        calls.clear()
        key_down(0x12)
        wait(app, 60)
        key_down(0x57)
        wait(app, 300)
        start_index = ctrl.wheel.index
        wheel_event(120)
        wait(app, 120)
        wheel_event(120)
        wait(app, 200)
        check("滚轮切换选中", ctrl.wheel.index != start_index, ctrl.wheel.index)
        key_up(0x57)
        wait(app, 60)
        key_up(0x12)
        wait(app, 1200)
        check("滚轮选中后执行", len(calls) == 1, calls)

        # ---------- 7. 屏幕居中模式
        print("== 居中模式 ==")
        wheel_cfg["select_mode"] = cfgmod.SELECT_MOUSE
        wheel_cfg["position_mode"] = cfgmod.POSITION_CENTER
        calls.clear()
        key_down(0x12)
        wait(app, 60)
        key_down(0x57)
        wait(app, 320)
        screen = app.primaryScreen().availableGeometry()
        scx, scy = ctrl.wheel.center_global()
        check("居中定位到屏幕中心",
              abs(scx - (screen.x() + screen.width() / 2)) < 40 and abs(scy - (screen.y() + screen.height() / 2)) < 40,
              "wheel=(%.0f,%.0f) screen=(%.0f,%.0f)" % (scx, scy, screen.x() + screen.width() / 2, screen.y() + screen.height() / 2))
        key_down(0x1B)
        wait(app, 100)
        key_up(0x1B)
        key_up(0x57)
        wait(app, 300)
        key_up(0x12)
        wait(app, 300)

        # ---------- 8. 多轮盘热键分发
        print("== 多轮盘 ==")
        wheel_cfg["position_mode"] = cfgmod.POSITION_CURSOR
        second = cfgmod.make_wheel(name="第二轮盘", hotkey_label="Alt+E", count=6)
        ctrl.cfg["wheels"].append(second)
        key_down(0x12)
        wait(app, 60)
        key_down(0x45)  # E
        wait(app, 340)
        cur = ctrl.wheel.wheel_config() or {}
        check("Alt+E 呼出第二个轮盘", cur.get("name") == "第二轮盘", cur.get("name"))
        check("第二个轮盘为 6 块", len(cur.get("segments") or []) == 6, len(cur.get("segments") or []))
        key_down(0x1B)
        wait(app, 120)
        key_up(0x1B)
        key_up(0x45)
        wait(app, 260)
        key_up(0x12)
        wait(app, 300)
        check("取消后回到未激活", not ctrl.wheel.active)
        ctrl.cfg["wheels"].pop()

        # ---------- 9. 未注册的热键不应触发
        print("== 无关按键 ==")
        key_down(0x12)
        wait(app, 60)
        key_down(0x54)  # Alt+T，未配置
        wait(app, 260)
        check("未配置的热键不呼出", not ctrl.wheel.active)
        key_up(0x54)
        key_up(0x12)
        wait(app, 200)

    finally:
        actions.execute = real_execute
        ctrl.shutdown()
        ctrl.wheel.finish_close()

    print("\n" + "=" * 40)
    print("通过 %d 项，失败 %d 项" % (PASS, FAIL))
    print("=" * 40)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
