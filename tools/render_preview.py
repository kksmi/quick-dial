# -*- coding: utf-8 -*-
"""把转盘渲染成 PNG，用于人工检查视觉效果（不参与打包）。"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import config as cfgmod  # noqa: E402
from app import theme  # noqa: E402
from app.radial import draw_wheel  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "assets")


def render(wheel, index, size=520, hint="松开 Alt+W 执行 · Esc 取消"):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    radius = size / 2 / 1.30 * 0.98
    lifts = [1.0 if i == index else 0.0 for i in range(len(wheel["segments"]))]
    draw_wheel(p, size / 2, size / 2, radius, wheel, index=index, lifts=lifts, opacity=1.0, hint=hint)
    p.end()
    return img


def compose(img, bg_top="#101826", bg_bottom="#1B2436"):
    """贴一个深色背景，模拟真实桌面。"""
    out = QImage(img.width() + 40, img.height() + 40, QImage.Format_ARGB32)
    p = QPainter(out)
    p.fillRect(out.rect(), QColor(bg_top))
    p.drawImage(20, 20, img)
    p.end()
    return out


def main():
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    os.makedirs(OUT, exist_ok=True)

    w8 = cfgmod.make_wheel(count=8)
    compose(render(w8, 1)).save(os.path.join(OUT, "preview_8.png"))

    w5 = cfgmod.make_wheel(count=5)
    compose(render(w5, 3)).save(os.path.join(OUT, "preview_5.png"))

    w10 = cfgmod.make_wheel(count=10)
    compose(render(w10, 6)).save(os.path.join(OUT, "preview_10.png"))

    w2 = cfgmod.make_wheel(count=2)
    compose(render(w2, 0)).save(os.path.join(OUT, "preview_2.png"))

    # 主题色板横排
    tiles = []
    for key in theme.THEME_ORDER:
        wk = cfgmod.make_wheel(count=6, theme_key=key)
        wk["theme"] = key
        pal = theme.get_palette(key)
        wk["accent"] = pal[0]
        for i, seg in enumerate(wk["segments"]):
            seg["color"] = pal[i % len(pal)]
        tiles.append(render(wk, 0, size=300, hint=""))

    cols = 4
    cell = 300
    board = QImage(cols * cell, 2 * cell, QImage.Format_ARGB32)
    board.fill(QColor("#101826"))
    p = QPainter(board)
    for i, t in enumerate(tiles):
        p.drawImage((i % cols) * cell, (i // cols) * cell, t)
    p.end()
    board.save(os.path.join(OUT, "preview_themes.png"))
    print("saved to", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
