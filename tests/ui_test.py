# -*- coding: utf-8 -*-
"""设置界面逻辑测试（离屏）：标签页、扇区增删、配色切换、热键冲突检测。"""

import os
import sys

# 统一 UTF-8 输出：Windows 默认控制台编码可能是 cp1252/gbk，打印中文会直接抛异常
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from app import config as cfgmod  # noqa: E402
from app import settings_ui  # noqa: E402

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] %s" % name)
    else:
        FAIL += 1
        print("  [FAIL] %s  %s" % (name, detail))


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    # 屏蔽模态框，避免离屏测试卡住
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

    saved = {}
    cfg = cfgmod.default_config()
    w = settings_ui.SettingsWindow(cfg, on_saved=lambda c: saved.update(cfg=c))
    w.show()
    app.processEvents()

    print("== 标签页 ==")
    check("初始 1 个标签", w.tabbar.count() == 1, w.tabbar.count())
    w._add_wheel()
    check("新建后 2 个标签", w.tabbar.count() == 2, w.tabbar.count())
    check("新轮盘热键不与已有重复",
          w._cfg["wheels"][0]["hotkey"]["label"] != w._cfg["wheels"][1]["hotkey"]["label"])

    print("== 热键冲突检测 ==")
    first_hotkey = w._cfg["wheels"][0]["hotkey"]["label"]
    w.tabbar.setCurrentIndex(1)
    w._on_hotkey_changed(first_hotkey)
    check("与其它轮盘重复 -> 提示冲突", "冲突" in w.hotkey_status.text(), w.hotkey_status.text())
    blocked = {"called": False}
    w._on_saved = lambda c: blocked.update(called=True)
    w._save()
    check("冲突时拒绝保存", not blocked["called"])

    w._on_hotkey_changed("Alt+F9")
    check("换成不冲突的键 -> 可用", "可用" in w.hotkey_status.text(), w.hotkey_status.text())
    w._save()
    check("无冲突时可保存", blocked["called"])

    print("== 扇区编辑 ==")
    w2 = settings_ui.SettingsWindow(cfgmod.default_config(), on_saved=lambda c: None)
    w2.show()
    app.processEvents()
    check("默认 8 行", w2.table.rowCount() == 8, w2.table.rowCount())
    w2.count_spin.setValue(5)
    check("改为 5 块后表格 5 行", w2.table.rowCount() == 5, w2.table.rowCount())
    check("配置同步为 5 段", len(w2._wheel()["segments"]) == 5)
    w2.count_spin.setValue(10)
    check("扩到 10 块", w2.table.rowCount() == 10, w2.table.rowCount())
    check("配置同步为 10 段", len(w2._wheel()["segments"]) == 10)

    # 改名称与动作内容
    w2._on_name_changed("我的轮盘")
    check("名称写回配置", w2._wheel()["name"] == "我的轮盘")
    check("标签文字同步", w2.tabbar.tabText(0) == "我的轮盘", w2.tabbar.tabText(0))

    print("== 分区按键录制 ==")
    from app.settings_ui import RecordButton

    holder = w2.table.cellWidget(0, 3)
    btn = holder.findChild(RecordButton) if holder else None
    check("按键动作改用录制控件", btn is not None)

    if btn is not None:
        # 录制组合键
        btn._recording = True
        btn.keyPressEvent(
            QKeyEvent(QEvent.KeyPress, Qt.Key_K, Qt.ControlModifier | Qt.AltModifier)
        )
        check("录制 Ctrl+Alt+K 写回配置",
              w2._wheel()["segments"][0]["action"]["value"] == "Ctrl+Alt+K",
              w2._wheel()["segments"][0]["action"]["value"])
        check("按钮显示录制结果", btn.text() == "Ctrl+Alt+K", btn.text())

        # 录制单键（组合键可以只有一个键）
        btn._recording = True
        btn.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_F7, Qt.NoModifier))
        check("录制单键 F7",
              w2._wheel()["segments"][0]["action"]["value"] == "F7",
              w2._wheel()["segments"][0]["action"]["value"])

        # 右键清除
        btn._label = ""
        btn.set_label("")
        btn.captured.emit("")
        check("右键清除后为空", w2._wheel()["segments"][0]["action"]["value"] == "")

        # 切换动作类型后控件类型应变化
        w2.table._on_type(0, cfgmod.ACTION_URL)
        holder2 = w2.table.cellWidget(0, 3)
        from PySide6.QtWidgets import QLineEdit
        check("切到网页类型后变输入框", holder2.findChild(QLineEdit) is not None)
        w2.table._on_type(0, cfgmod.ACTION_KEYS)

    print("== 分区顺序调整 ==")
    w5 = settings_ui.SettingsWindow(cfgmod.default_config(), on_saved=lambda c: None)
    w5.show()
    app.processEvents()
    check("表格有 5 列（含顺序列）", w5.table.columnCount() == 5, w5.table.columnCount())
    names_before = [s["name"] for s in w5._wheel()["segments"]]
    colors_before = [s["color"] for s in w5._wheel()["segments"]]

    w5.table.move_row(0, 1)
    segs = w5._wheel()["segments"]
    check("下移：第 0 与第 1 互换", segs[0]["name"] == names_before[1] and segs[1]["name"] == names_before[0],
          [s["name"] for s in segs[:2]])
    check("颜色随分区一起移动", segs[0]["color"] == colors_before[1], segs[0]["color"])
    check("表格行同步更新", w5.table.cellWidget(0, 1).text() == names_before[1])

    w5.table.move_row(1, -1)
    check("上移可复原", [s["name"] for s in w5._wheel()["segments"]] == names_before)

    w5.table.move_row(0, -1)
    check("首行上移不越界", [s["name"] for s in w5._wheel()["segments"]] == names_before)
    last = len(names_before) - 1
    w5.table.move_row(last, 1)
    check("末行下移不越界", [s["name"] for s in w5._wheel()["segments"]] == names_before)

    w5.count_spin.setValue(12)
    check("分区上限 12", w5.table.rowCount() == 12, w5.table.rowCount())
    check("配置同步 12 段", len(w5._wheel()["segments"]) == 12)

    print("== 配色 ==")
    old_color = w2._wheel()["segments"][0]["color"]
    idx = w2.theme_combo.findData("sunset")
    w2.theme_combo.setCurrentIndex(idx)
    new_color = w2._wheel()["segments"][0]["color"]
    check("切换主题改变主色", w2._wheel()["accent"] == "#F97316", w2._wheel()["accent"])
    check("切换主题重设扇区色", new_color != old_color, "%s -> %s" % (old_color, new_color))

    # 单块颜色
    w2.table._on_color(0, "#123456")
    check("单块颜色写回", w2._wheel()["segments"][0]["color"] == "#123456")

    print("== 录制期间挂起热键 ==")
    rec_states = []
    w4 = settings_ui.SettingsWindow(
        cfgmod.default_config(), on_saved=lambda c: None, on_recording=rec_states.append
    )
    w4.show()
    app.processEvents()
    btn4 = w4.table.cellWidget(0, 3).findChild(settings_ui.RecordButton)
    check("表格里有录制按钮", btn4 is not None)
    if btn4 is not None:
        btn4._set_recording(True)
        check("开始录制通知外部挂起热键", rec_states == [True], rec_states)
        btn4._set_recording(False)
        check("结束录制通知外部恢复热键", rec_states == [True, False], rec_states)

    print("== 删除保护 ==")
    w3 = settings_ui.SettingsWindow(cfgmod.default_config(), on_saved=lambda c: None)
    w3.show()
    app.processEvents()
    w3._remove_wheel()
    check("只剩一个时不能删除", len(w3._cfg["wheels"]) == 1, len(w3._cfg["wheels"]))

    print("== 参数边界 ==")
    w3.size_slider.setValue(cfgmod.DIAMETER_MAX + 200)
    check("大小被限制在上限", w3._wheel()["diameter"] == cfgmod.DIAMETER_MAX, w3._wheel()["diameter"])
    w3.sens_slider.setValue(10)
    check("灵敏度写回", w3._wheel()["sensitivity"] == 10)

    print("\n" + "=" * 40)
    print("通过 %d 项，失败 %d 项" % (PASS, FAIL))
    print("=" * 40)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
