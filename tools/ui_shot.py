# -*- coding: utf-8 -*-
"""抓取设置界面截图，用于人工检查布局（不参与打包）。"""
import os, sys
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
