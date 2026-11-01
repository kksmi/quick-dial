# -*- coding: utf-8 -*-
"""抓取设置界面截图，用于人工检查布局（不参与打包）。"""
import os, sys

# 统一 UTF-8 输出：Windows 默认控制台编码可能是 cp1252/gbk，打印中文会直接抛异常
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
from app import config as cfgmod, theme
from app.settings_ui import SettingsWindow

app = QApplication(sys.argv)
app.setStyleSheet(theme.app_stylesheet())
cfg = cfgmod.default_config()
w = SettingsWindow(cfg, on_saved=None)
w.show()
app.processEvents()
for _ in range(3):
    app.processEvents()
img = w.grab().toImage()
out = QImage(img.width() + 24, img.height() + 24, QImage.Format_ARGB32)
out.fill(QColor("#E8ECF5"))
p = QPainter(out); p.drawImage(12, 12, img); p.end()
path = os.path.join(os.path.dirname(__file__), "..", "assets", "ui_settings.png")
out.save(path)
print("saved", path, out.width(), out.height())
