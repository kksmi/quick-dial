# -*- coding: utf-8 -*-
"""无界面自测：按键映射 / 配置容错 / 角度选中 / 离屏渲染 / 钩子安装。

运行：.venv\\Scripts\\python.exe tests\\selftest.py
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import config as cfgmod  # noqa: E402
from app import keys as keymod  # noqa: E402
from app import native  # noqa: E402
from app.radial import RadialWheel, draw_wheel  # noqa: E402

PASS = 0
FAIL = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] %s" % name)
    else:
        FAIL += 1
        FAILURES.append("%s %s" % (name, detail))
        print("  [FAIL] %s  %s" % (name, detail))


def section(title):
    print("\n== %s ==" % title)


# ------------------------------------------------------------------ keys
def test_keys():
    section("按键映射")
    cases = [
        ("Ctrl+C", ["ctrl"], 0x43),
        ("Alt+Q", ["alt"], 0x51),
        ("Win+Shift+S", ["win", "shift"], 0x53),
        ("F9", [], 0x78),
        ("Ctrl+Alt+Delete", ["ctrl", "alt"], 0x2E),
        ("Ctrl+,", ["ctrl"], 0xBC),
        ("Num5", [], 0x65),
        ("VolumeUp", [], 0xAF),
    ]
    for label, mods, vk in cases:
        m, v = keymod.parse_label(label)
        check("解析 %s" % label, m is not None and set(m) == set(mods) and v == vk, "得到 %s/%s" % (m, v))
        check("生成 %s" % label, keymod.make_label(mods, vk) == label, keymod.make_label(mods, vk))

    check("无法解析的标签返回 None", keymod.parse_label("Ctrl+上上下下")[0] is None)
    check("纯修饰键被拒绝", keymod.parse_label("Ctrl")[0] is None)

    # Qt 键码 -> 标签
    check("Qt A -> A", keymod.label_from_qt(int(Qt.Key_A), 0) == "A")
    check("Qt Ctrl+C", keymod.label_from_qt(int(Qt.Key_C), Qt.ControlModifier.value) == "Ctrl+C")
    check("Qt F5", keymod.label_from_qt(int(Qt.Key_F5), 0) == "F5")
    check("Qt Alt+Left", keymod.label_from_qt(int(Qt.Key_Left), Qt.AltModifier.value) == "Alt+Left")
    check("Qt Win+Shift+S", keymod.label_from_qt(int(Qt.Key_S), Qt.MetaModifier.value | Qt.ShiftModifier.value) == "Win+Shift+S")
    check("Qt 小键盘 5", keymod.label_from_qt(0x35, Qt.KeypadModifier.value) == "Num5")

    check("系统保留：Alt+Tab", keymod.check_reserved(["alt"], 0x09) is not None)
    check("非保留：Alt+Q", keymod.check_reserved(["alt"], 0x51) is None)


# ------------------------------------------------------------------ config
def test_config():
    section("配置模型")
    cfg = cfgmod.default_config()
    check("默认轮盘数量", len(cfg["wheels"]) == 1)
    wheel = cfg["wheels"][0]
    check("默认扇区 = 8", len(wheel["segments"]) == 8)
    check("默认热键 Alt+W", wheel["hotkey"]["label"] == "Alt+W")
    check("默认直径", wheel["diameter"] == cfgmod.DIAMETER_DEFAULT)

    # 容错：垃圾输入
    junk = {
        "wheels": [
            {"name": 123, "hotkey": "%%%", "diameter": "abc", "sensitivity": 99,
             "segments": [{"name": None, "color": "红色", "action": "not-a-dict"}, {}]},
            "我不是字典",
        ],
        "launch_at_startup": "yes",
    }
    norm = cfgmod.normalize_config(junk)
    check("垃圾配置不抛异常", isinstance(norm, dict))
    check("两个轮盘都被保留", len(norm["wheels"]) == 2)
    w0 = norm["wheels"][0]
    check("名称被强制为字符串", isinstance(w0["name"], str))
    check("直径回落到默认", w0["diameter"] == cfgmod.DIAMETER_DEFAULT)
    check("灵敏度被夹到 10", w0["sensitivity"] == 10)
    check("非法颜色被替换", all(seg["color"].startswith("#") for seg in w0["segments"]))
    check("段数至少为 2", len(w0["segments"]) >= 2)
    check("动作被规范化", all(isinstance(s["action"], dict) for s in w0["segments"]))

    # 扇区数量调整
    w = cfgmod.normalize_wheel(cfgmod.make_wheel())
    cfgmod.resize_segments(w, 3)
    check("缩到 3 段", len(w["segments"]) == 3)
    cfgmod.resize_segments(w, 10)
    check("扩到 10 段", len(w["segments"]) == 10)
    cfgmod.resize_segments(w, 99)
    check("超上限被夹到 10", len(w["segments"]) == 10)

    # 读写往返
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "c.json")
        cfgmod.save_config(cfg, path)
        back = cfgmod.load_config(path)
        check("读写往返一致", back["wheels"][0]["hotkey"]["label"] == "Alt+W")
        check("读不存在文件给默认", len(cfgmod.load_config(os.path.join(tmp, "none.json"))["wheels"]) == 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{坏掉的 json")
        check("坏文件不抛异常", len(cfgmod.load_config(path)["wheels"]) == 1)


# ------------------------------------------------------------------ 角度选中
def test_selection(app):
    section("角度选中（鼠标模式）")
    wheel_cfg = cfgmod.make_wheel(count=8)
    wheel_cfg["diameter"] = 400
    wheel_cfg["sensitivity"] = 6
    w = RadialWheel()
    w.open_wheel(wheel_cfg, anchor_x=400, anchor_y=400, hint="test")
    app.processEvents()

    cx, cy = w.center_global()
    r = w.radius()
    print("    圆心=(%.1f, %.1f) 半径=%.1f 窗口=%s" % (cx, cy, r, w.geometry()))

    def pick(dx, dy):
        w._index = -1  # 重置，避免上一次滞后影响
        w.update_from_cursor(cx + dx, cy + dy)
        return w.index

    d = r * 0.8
    check("正上方 -> 0", pick(0, -d) == 0, pick(0, -d))
    check("右上 45° -> 1", pick(d * 0.707, -d * 0.707) == 1)
    check("正右 -> 2", pick(d, 0) == 2)
    check("右下 45° -> 3", pick(d * 0.707, d * 0.707) == 3)
    check("正下 -> 4", pick(0, d) == 4)
    check("左下 45° -> 5", pick(-d * 0.707, d * 0.707) == 5)
    check("正左 -> 6", pick(-d, 0) == 6)
    check("左上 45° -> 7", pick(-d * 0.707, -d * 0.707) == 7)

    # 死区：圆内很近处不改变选中
    w._index = 2
    w.update_from_cursor(cx + 5, cy + 5)
    check("死区内保持原选中", w.index == 2, w.index)

    # 滚轮模式
    wheel_cfg2 = cfgmod.make_wheel(count=6)
    wheel_cfg2["select_mode"] = cfgmod.SELECT_WHEEL
    w.open_wheel(wheel_cfg2, anchor_x=400, anchor_y=400)
    check("滚轮模式初始选中 0", w.index == 0)
    w.cycle(1)
    w.cycle(1)
    check("向下滚两格 -> 2", w.index == 2, w.index)
    w.cycle(-1)
    check("向上滚一格 -> 1", w.index == 1, w.index)
    w.cycle(-1)
    w.cycle(-1)
    check("循环到末尾 -> 5", w.index == 5, w.index)
    w.finish_close()

    # 非 8 分区的边界：12 块不可能（上限 10），用 10 块验证
    wheel_cfg3 = cfgmod.make_wheel(count=10)
    wheel_cfg3["diameter"] = 400
    w.open_wheel(wheel_cfg3, anchor_x=400, anchor_y=400)
    cx, cy = w.center_global()
    d = w.radius() * 0.8
    check("10 块：正上方 -> 0", pick(0, -d) == 0)
    check("10 块：正右 -> 2 或 3", pick(d, 0) in (2, 3), pick(d, 0))
    w.finish_close()
    w.deleteLater()


# ------------------------------------------------------------------ 渲染
def test_render():
    section("离屏渲染")
    wheel = cfgmod.make_wheel(count=8)
    img = QImage(420, 420, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    try:
        draw_wheel(p, 210, 210, 170, wheel, index=1, lifts=[0, 1, 0, 0, 0, 0, 0, 0], opacity=1.0, hint="松开 Alt+Q 执行")
        ok = True
        err = ""
    except Exception as exc:  # noqa: BLE001
        ok = False
        err = "%s: %s" % (type(exc).__name__, exc)
    p.end()
    check("绘制不抛异常", ok, err)
    center = img.pixelColor(210, 210)
    check("中心有内容", center.alpha() > 0, center.getRgb())
    corner = img.pixelColor(4, 4)
    check("角落保持透明", corner.alpha() < 20, corner.getRgb())
    # 采样选中的扇区（正上方 45° 方向）
    px = img.pixelColor(210 + 120, 210 - 120)
    check("扇区已绘制", px.alpha() > 100, px.getRgb())

    # 极端参数：2 块 / 10 块 / 最小直径 / 最大直径
    for n in (2, 10):
        for dia in (180, 760):
            wk = cfgmod.make_wheel(count=n)
            wk["diameter"] = dia
            im2 = QImage(int(dia * 1.3) + 2, int(dia * 1.3) + 2, QImage.Format_ARGB32)
            im2.fill(QColor(0, 0, 0, 0))
            pp = QPainter(im2)
            try:
                draw_wheel(pp, im2.width() / 2, im2.height() / 2, dia / 2, wk, index=0, hint="hi")
                ok = True
            except Exception as exc:  # noqa: BLE001
                ok = False
                err = str(exc)
            pp.end()
            check("渲染 %d 块 / %dpx" % (n, dia), ok, "" if ok else err)


# ------------------------------------------------------------------ 钩子
def test_hooks():
    section("全局钩子")
    if os.environ.get("QUICKDIAL_SKIP_HOOKS") == "1":
        print("  已跳过（无桌面会话的环境无法安装全局钩子）")
        x, y = native.get_cursor_pos()
        check("可获取光标位置", isinstance(x, int) and isinstance(y, int), (x, y))
        return
    seen = []

    def on_key(vk, down):
        seen.append((vk, down))
        return False

    hooks = native.InputHooks(on_key, lambda d: False)
    ok = hooks.start()
    check("键盘钩子安装成功", ok)
    if ok:
        import ctypes
        import time

        # 注入 F24：钩子能收到，但会被 injected 标记过滤（不应进入业务回调）
        class KBD(ctypes.Structure):
            _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                        ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                        ("dwExtraInfo", ctypes.c_size_t)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong), ("ki", KBD), ("pad", ctypes.c_byte * 8)]

        inp = INPUT()
        inp.type = 1
        inp.ki.wVk = 0x87  # F24
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.15)
        up = INPUT()
        up.type = 1
        up.ki.wVk = 0x87
        up.ki.dwFlags = 2
        ctypes.windll.user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
        time.sleep(0.15)
        check("注入按键被过滤（不会误触发热键）", len(seen) == 0, seen)
        hooks.stop()
        check("钩子可正常卸载", not hooks.alive)

    # 光标位置
    x, y = native.get_cursor_pos()
    check("可获取光标位置", isinstance(x, int) and isinstance(y, int), (x, y))

    free, reason = native.probe_hotkey(0x57, ["alt"])
    check("热键探测返回有效结果", isinstance(free, bool) and isinstance(reason, str), (free, reason))
    print("    探测 Alt+W：%s %s" % ("空闲" if free else "被占用", reason))


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    test_keys()
    test_config()
    test_selection(app)
    test_render()
    test_hooks()

    print("\n" + "=" * 46)
    print("通过 %d 项，失败 %d 项" % (PASS, FAIL))
    if FAILURES:
        print("失败清单：")
        for f in FAILURES:
            print("  - " + f)
    print("=" * 46)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
