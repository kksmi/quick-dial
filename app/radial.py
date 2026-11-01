# -*- coding: utf-8 -*-
"""转盘渲染与交互窗口。

绘制逻辑抽成模块级函数 draw_wheel，运行窗口与设置页实时预览共用同一套实现，
避免"预览和实际不一样"这类常见问题。
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QCursor,
)
from PySide6.QtWidgets import QWidget

from . import config as cfgmod
from . import theme

WINDOW_SCALE = 1.30  # 窗口边长 / 转盘直径，给浮出与光晕留空间
FONT_FAMILY = "Microsoft YaHei UI"


def _sector_path(cx, cy, r_in, r_out, a_start, sweep):
    """构造一个环形扇区路径。a_start 为 Qt 角度（0°=3 点方向，逆时针为正），
    sweep 为顺时针扫过角度（正值）。"""
    outer = QRectF(cx - r_out, cy - r_out, r_out * 2, r_out * 2)
    inner = QRectF(cx - r_in, cy - r_in, r_in * 2, r_in * 2)
    path = QPainterPath()
    path.arcMoveTo(outer, a_start)
    path.arcTo(outer, a_start, -sweep)
    path.arcTo(inner, a_start - sweep, sweep)
    path.closeSubpath()
    return path


def _fit_font(painter, text, max_width, size_px, bold=False):
    """返回在 max_width 内放得下的字体。"""
    f = QFont(FONT_FAMILY)
    f.setPixelSize(max(9, int(size_px)))
    f.setBold(bold)
    fm = QFontMetrics(f)
    if max_width > 10 and fm.horizontalAdvance(text) > max_width:
        # 按比例收缩，最低 9px，再不行交给 elidedText 截断
        target = max(9, int(size_px * max_width / max(1, fm.horizontalAdvance(text))))
        f.setPixelSize(target)
    return f


def _elide(text, font, max_width):
    fm = QFontMetrics(font)
    if max_width <= 10:
        return text
    return fm.elidedText(text, Qt.ElideRight, int(max_width))


def draw_wheel(
    painter,
    cx,
    cy,
    radius,
    wheel,
    index=-1,
    lifts=None,
    opacity=1.0,
    hint="",
    detailed=True,
):
    """绘制转盘。cx/cy 为圆心，radius 为转盘半径。"""
    segments = wheel.get("segments") or []
    n = len(segments)
    if n <= 0:
        return
    accent = wheel.get("accent") or theme.get_palette(wheel.get("theme", theme.DEFAULT_THEME))[0]
    if lifts is None:
        lifts = [1.0 if i == index else 0.0 for i in range(n)]
    elif len(lifts) < n:
        lifts = list(lifts) + [0.0] * (n - len(lifts))

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    painter.setOpacity(max(0.0, min(1.0, opacity)))

    span_deg = 360.0 / n
    gap_deg = min(2.4, span_deg * 0.10)
    r_in = radius * 0.315
    base_out = radius

    # ---------------- 背光
    glow = QRadialGradient(cx, cy, radius * 1.22)
    gc = QColor(accent)
    gc.setAlpha(58)
    glow.setColorAt(0.55, gc)
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(glow)
    painter.drawEllipse(QPointF(cx, cy), radius * 1.22, radius * 1.22)

    # ---------------- 底板（带主色色调，让"转盘主色"有可见效果）
    plate = QColor(theme.mix(accent, "#090D15", 0.87))
    plate.setAlpha(170)
    painter.setBrush(plate)
    painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
    painter.drawEllipse(QPointF(cx, cy), radius * 1.045, radius * 1.045)

    # ---------------- 扇区
    for i, seg in enumerate(segments):
        lift = max(0.0, min(1.0, lifts[i]))
        color = seg.get("color") or accent
        mid_deg = i * span_deg
        a_center = 90.0 - mid_deg
        half = span_deg / 2.0
        a_start = a_center + half - gap_deg / 2.0
        sweep = span_deg - gap_deg

        # 浮出：外扩 + 沿中角方向轻微外移
        r_out = base_out * (1.0 + 0.035 * lift)
        offset = base_out * 0.045 * lift
        rad = math.radians(mid_deg)
        ox = cx + math.sin(rad) * offset
        oy = cy - math.cos(rad) * offset

        path = _sector_path(ox, oy, r_in, r_out, a_start, sweep)

        if lift > 0.02 and detailed:
            # 投影：同形状偏移绘制，模拟轻微悬浮
            shadow = QPainterPath(path)
            painter.save()
            painter.translate(0, 3.0 * lift)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, int(90 * lift)))
            painter.drawPath(shadow)
            painter.restore()

        fill = QColor(color)
        if lift > 0.01:
            fill = QColor(theme.mix(color, "#FFFFFF", 0.16 * lift))
        fill.setAlpha(226 if lift < 0.4 else 246)
        painter.setBrush(fill)
        if lift > 0.02:
            painter.setPen(QPen(QColor(255, 255, 255, int(70 + 120 * lift)), 1.0 + 1.2 * lift))
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
        painter.drawPath(path)

        # ---------------- 扇区文字
        text_color = QColor(theme.text_on(fill.name()))
        label = str(seg.get("name") or "")
        if not label:
            continue
        r_mid = r_in + (r_out - r_in) * 0.56
        tx = ox + math.sin(rad) * r_mid
        ty = oy - math.cos(rad) * r_mid
        avail_w = 2.0 * r_mid * math.sin(math.radians(span_deg / 2.0)) - 12.0
        size = min(radius * (0.115 if n <= 6 else 0.10), 22.0)
        font = _fit_font(painter, label, avail_w, size, bold=lift > 0.5)
        painter.setFont(font)
        text_color.setAlpha(int(235 + 20 * lift))
        painter.setPen(QPen(text_color))
        shown = _elide(label, font, avail_w)
        fm = QFontMetrics(font)
        mh = fm.height()
        painter.drawText(
            QRectF(tx - avail_w / 2.0, ty - mh / 2.0, avail_w, mh),
            int(Qt.AlignCenter),
            shown,
        )

        # 动作快捷键小字
        action = seg.get("action") or {}
        sub = ""
        if action.get("type") == cfgmod.ACTION_KEYS:
            sub = str(action.get("value") or "")
        elif action.get("type") == cfgmod.ACTION_URL:
            sub = "网址"
        elif action.get("type") == cfgmod.ACTION_MEDIA:
            sub = dict(cfgmod.MEDIA_ACTIONS).get(action.get("value"), "")
        elif action.get("type") == cfgmod.ACTION_LAUNCH:
            sub = "打开"
        if sub and detailed and radius >= 110:
            sf = QFont(FONT_FAMILY)
            sf.setPixelSize(max(8, int(size * 0.62)))
            painter.setFont(sf)
            sub_color = QColor(theme.text_on(fill.name()))
            sub_color.setAlpha(150)
            painter.setPen(QPen(sub_color))
            painter.drawText(
                QRectF(tx - avail_w / 2.0, ty + mh * 0.42, avail_w, mh * 0.8),
                int(Qt.AlignCenter),
                _elide(sub, sf, avail_w),
            )

    # ---------------- 内圈分隔环
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor(255, 255, 255, 40), 1.2))
    painter.drawEllipse(QPointF(cx, cy), r_in, r_in)

    # ---------------- 中心圆
    center_r = r_in * 0.94
    selected = segments[index] if 0 <= index < n else None
    center_bg = QColor(theme.mix(accent, "#090D15", 0.85))
    center_bg.setAlpha(238)
    if selected:
        center_bg = QColor(theme.mix(selected.get("color") or accent, "#0B1018", 0.72))
        center_bg.setAlpha(244)
    painter.setBrush(center_bg)
    painter.setPen(QPen(QColor(255, 255, 255, 34), 1.0))
    painter.drawEllipse(QPointF(cx, cy), center_r, center_r)

    if detailed and center_r > 26:
        title = selected.get("name") if selected else str(wheel.get("name") or "")
        sub_line = ""
        if selected:
            action = selected.get("action") or {}
            atype = action.get("type")
            if atype == cfgmod.ACTION_KEYS:
                sub_line = str(action.get("value") or "未设置")
            elif atype == cfgmod.ACTION_URL:
                sub_line = str(action.get("value") or "未设置")
            elif atype == cfgmod.ACTION_MEDIA:
                sub_line = dict(cfgmod.MEDIA_ACTIONS).get(action.get("value"), "")
            else:
                sub_line = str(action.get("value") or "未设置")
        else:
            sub_line = "移动鼠标选择" if wheel.get("select_mode") == cfgmod.SELECT_MOUSE else "滚动滚轮选择"

        box_w = center_r * 1.68
        tf = _fit_font(painter, str(title or ""), box_w, min(center_r * 0.42, 20), bold=True)
        painter.setFont(tf)
        painter.setPen(QPen(QColor(255, 255, 255, 240)))
        fm = QFontMetrics(tf)
        painter.drawText(
            QRectF(cx - box_w / 2, cy - fm.height() * 0.95, box_w, fm.height()),
            int(Qt.AlignCenter),
            _elide(str(title or ""), tf, box_w),
        )
        sf = QFont(FONT_FAMILY)
        sf.setPixelSize(max(9, int(center_r * 0.24)))
        painter.setFont(sf)
        painter.setPen(QPen(QColor(255, 255, 255, 150)))
        fm2 = QFontMetrics(sf)
        painter.drawText(
            QRectF(cx - box_w / 2, cy + fm.height() * 0.15, box_w, fm2.height()),
            int(Qt.AlignCenter),
            _elide(sub_line, sf, box_w),
        )

    # ---------------- 底部提示胶囊
    if detailed and hint:
        hf = QFont(FONT_FAMILY)
        hf.setPixelSize(max(10, int(radius * 0.085)))
        fm = QFontMetrics(hf)
        tw = fm.horizontalAdvance(hint) + 26
        th = fm.height() + 12
        hy = cy + radius * 1.10
        rect = QRectF(cx - tw / 2, hy - th / 2, tw, th)
        painter.setBrush(QColor(10, 14, 22, 190))
        painter.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
        painter.drawRoundedRect(rect, th / 2, th / 2)
        painter.setFont(hf)
        painter.setPen(QPen(QColor(255, 255, 255, 190)))
        painter.drawText(rect, int(Qt.AlignCenter), hint)

    painter.restore()


class RadialWheel(QWidget):
    """屏幕上实际出现的转盘窗口。

    - 鼠标穿透：窗口不拦截鼠标，光标外观不变，也不会把下面的窗口失焦；
    - 选中靠主程序轮询光标位置 / 全局滚轮钩子驱动，因此窗口无需接收输入。
    """

    committed = Signal(int)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
            | Qt.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)

        self._wheel = None
        self._index = -1
        self._lifts = []
        self._fade = 0.0
        self._hint = ""
        self._closing = False
        self._active = False

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------ 状态
    @property
    def active(self):
        return self._active

    @property
    def index(self):
        return self._index

    def radius(self):
        """实际半径：按窗口尺寸反推，屏幕边缘自动缩小时角度计算依然正确。"""
        if not self._wheel:
            return 0.0
        return self.width() / WINDOW_SCALE / 2.0

    def wheel_config(self):
        return self._wheel

    def center_global(self):
        geo = self.geometry()
        return geo.x() + geo.width() / 2.0, geo.y() + geo.height() / 2.0

    # ------------------------------------------------------------ 打开/关闭
    def open_wheel(self, wheel, anchor_x=None, anchor_y=None, hint=""):
        self._wheel = wheel
        n = len(wheel.get("segments") or [])
        self._lifts = [0.0] * n
        self._closing = False
        self._active = True
        self._hint = hint

        diameter = float(wheel.get("diameter", cfgmod.DIAMETER_DEFAULT))

        if wheel.get("position_mode") == cfgmod.POSITION_CENTER:
            if anchor_x is None:
                anchor_x, anchor_y = QCursor.pos().x(), QCursor.pos().y()
            screen = QGuiApplication.screenAt(QPointF(anchor_x, anchor_y).toPoint()) or QGuiApplication.primaryScreen()
            geo = screen.availableGeometry()
            cx = geo.x() + geo.width() / 2.0
            cy = geo.y() + geo.height() / 2.0
            screen_geo = geo
        else:
            if anchor_x is None:
                pt = QCursor.pos()
                anchor_x, anchor_y = pt.x(), pt.y()
            cx, cy = float(anchor_x), float(anchor_y)
            screen = QGuiApplication.screenAt(QPointF(anchor_x, anchor_y).toPoint()) or QGuiApplication.primaryScreen()
            screen_geo = screen.availableGeometry()

        # 光标贴近屏幕边缘时按可用空间等比缩小：
        # 保证"圆心严格落在光标上"（跟随语义），同时转盘本体完整可见。
        avail = min(
            cx - screen_geo.x(),
            screen_geo.right() - cx,
            cy - screen_geo.y(),
            screen_geo.bottom() - cy,
        )
        half_need = diameter / 2.0 * 1.04
        if avail < half_need:
            # 最多缩到 55%：再贴边就保持这个尺寸，让窗口自然超出屏幕，
            # 否则转盘会小到看不清分区名
            ratio = max(0.55, avail / half_need)
            diameter = max(120.0, diameter * ratio)

        size = max(150, int(round(diameter * WINDOW_SCALE)))
        x = int(round(cx - size / 2.0))
        y = int(round(cy - size / 2.0))

        self.setGeometry(x, y, size, size)

        # 初始选中：滚轮模式默认第一块；鼠标模式从"无选中"开始，需移动光标才选中
        self._index = 0 if wheel.get("select_mode") == cfgmod.SELECT_WHEEL else -1
        self._fade = 0.0
        self.show()
        self.raise_()
        self._timer.start()
        self.update()

    def close_wheel(self):
        if not self._active:
            return
        self._active = False
        self._closing = True
        if not self._timer.isActive():
            self._timer.start()

    def finish_close(self):
        self._timer.stop()
        self._closing = False
        self._fade = 0.0
        self.hide()
        self._wheel = None
        self._index = -1

    # ------------------------------------------------------------ 选中
    def set_index(self, idx):
        if not self._wheel:
            return
        n = len(self._wheel.get("segments") or [])
        if n == 0:
            return
        idx = idx % n
        if idx != self._index:
            self._index = idx
            self.update()

    def cycle(self, direction):
        """滚轮切换：direction = -1 上一个，+1 下一个。"""
        if not self._wheel:
            return
        n = len(self._wheel.get("segments") or [])
        if n == 0:
            return
        base = self._index if self._index >= 0 else 0
        self.set_index((base + direction) % n)

    def update_from_cursor(self, gx, gy):
        """鼠标模式：按光标相对圆心的角度选中。"""
        if not self._active or not self._wheel:
            return
        if self._wheel.get("select_mode") != cfgmod.SELECT_MOUSE:
            return
        n = len(self._wheel.get("segments") or [])
        if n == 0:
            return
        cx, cy = self.center_global()
        dx = gx - cx
        dy = gy - cy
        dist = math.hypot(dx, dy)
        radius = self.radius()
        if radius <= 1:
            return

        sens = int(self._wheel.get("sensitivity", 6))
        # 灵敏度越高，死区越小：s=1 -> 0.32R，s=10 -> 0.10R
        dead = radius * (0.34 - 0.024 * sens)
        if dist < dead:
            return  # 停留在死区内时保持已有选中，避免中心抖动导致误选

        theta = math.degrees(math.atan2(dx, -dy)) % 360.0
        span = 360.0 / n
        idx = int(((theta + span / 2.0) % 360.0) // span) % n

        # 角度滞后：必须离开当前扇区中心一定角度才切换，低灵敏度更迟钝
        if 0 <= self._index < n:
            cur_center = self._index * span
            diff = abs(((theta - cur_center + 180.0) % 360.0) - 180.0)
            lag = span * (0.5 + 0.14 * (10 - sens) / 9.0)
            if diff < lag:
                return
        self.set_index(idx)

    # ------------------------------------------------------------ 动画
    def _tick(self):
        if not self._wheel:
            self._timer.stop()
            return
        n = len(self._wheel.get("segments") or [])
        changed = False

        if self._closing:
            self._fade -= 0.18
            if self._fade <= 0.0:
                self.finish_close()
                return
            changed = True
        elif self._fade < 1.0:
            self._fade = min(1.0, self._fade + 0.22)
            changed = True

        for i in range(n):
            target = 1.0 if i == self._index else 0.0
            cur = self._lifts[i]
            if abs(cur - target) > 0.004:
                self._lifts[i] = cur + (target - cur) * 0.30
                changed = True
            elif cur != target:
                self._lifts[i] = target
                changed = True

        if changed:
            self.update()

    def paintEvent(self, event):
        if not self._wheel:
            return
        painter = QPainter(self)
        draw_wheel(
            painter,
            self.width() / 2.0,
            self.height() / 2.0,
            self.radius(),
            self._wheel,
            index=self._index,
            lifts=self._lifts,
            opacity=self._fade,
            hint=self._hint,
        )
        painter.end()


class WheelPreview(QWidget):
    """设置界面里的静态预览。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wheel = None
        self._index = -1
        self.setMinimumSize(260, 260)

    def set_wheel(self, wheel, index=0):
        self._wheel = wheel
        self._index = index
        self.update()

    def set_index(self, index):
        self._index = index
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if not self._wheel:
            painter.end()
            return
        w = self.width()
        h = self.height()
        radius = min(w, h) / 2.0 / WINDOW_SCALE * 0.98
        lifts = [0.0] * len(self._wheel.get("segments") or [])
        if 0 <= self._index < len(lifts):
            lifts[self._index] = 1.0
        draw_wheel(
            painter,
            w / 2.0,
            h / 2.0,
            radius,
            self._wheel,
            index=self._index,
            lifts=lifts,
            opacity=1.0,
            hint="",
            detailed=radius > 90,
        )
        painter.end()
