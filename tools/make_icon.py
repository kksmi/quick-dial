# -*- coding: utf-8 -*-
"""生成程序图标：多尺寸 PNG + 合并 ICO。"""

import os
import sys

# 统一 UTF-8 输出：Windows 默认控制台编码可能是 cp1252/gbk，打印中文会直接抛异常
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import theme  # noqa: E402

SIZES = [16, 24, 32, 48, 64, 128, 256]
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")


def draw_icon(size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)

    colors = theme.get_palette("aurora") + ["#38BDF8"]
    n = 8
    r = size * 0.475
    cx = cy = size / 2.0
    rect = QRectF(cx - r, cy - r, r * 2, r * 2)
    gap = max(0.6, 1.2 * size / 256.0)

    for i in range(n):
        a0 = (90 - i * 360.0 / n) + 360.0 / n / 2 - gap
        span = 360.0 / n - gap * 2
        p.setBrush(QColor(colors[i % len(colors)]))
        p.setPen(Qt.NoPen)
        p.drawPie(rect, int(a0 * 16), int(-span * 16))

    # 中心圆
    cr = r * 0.34
    p.setBrush(QColor(11, 16, 26))
    p.setPen(QPen(QColor(255, 255, 255, 60), max(0.8, size / 200.0)))
    p.drawEllipse(QRectF(cx - cr, cy - cr, cr * 2, cr * 2))
    p.end()
    return img


def main():
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    icon_dir = os.path.join(OUT, "icon")
    os.makedirs(icon_dir, exist_ok=True)
    paths = []
    for s in SIZES:
        path = os.path.join(icon_dir, "icon_%d.png" % s)
        draw_icon(s).save(path)
        paths.append(path)
    print("png done:", len(paths))

    # 用 Pillow 合并多尺寸 ICO（PyInstaller 与资源管理器都认）
    try:
        from PIL import Image

        imgs = [Image.open(p) for p in paths]
        imgs.sort(key=lambda im: im.width)
        ico = os.path.join(OUT, "app.ico")
        imgs[-1].save(ico, format="ICO", sizes=[(im.width, im.height) for im in imgs])
        print("ico:", ico, os.path.getsize(ico), "bytes")
    except ImportError:
        print("Pillow 不可用，跳过 ICO 合并")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
