# -*- coding: utf-8 -*-
"""配色主题：预设色板 + 颜色工具 + 界面样式表。"""

DEFAULT_THEME = "aurora"

# 每个色板 5 个颜色，扇区按序循环取色
PALETTES = {
    "aurora": {
        "name": "极光蓝",
        "colors": ["#3B82F6", "#22D3EE", "#6366F1", "#14B8A6", "#0EA5E9"],
    },
    "neon": {
        "name": "霓虹紫",
        "colors": ["#8B5CF6", "#D946EF", "#6366F1", "#EC4899", "#A855F7"],
    },
    "forest": {
        "name": "森野绿",
        "colors": ["#10B981", "#84CC16", "#14B8A6", "#22C55E", "#059669"],
    },
    "sunset": {
        "name": "落日橙",
        "colors": ["#F97316", "#F59E0B", "#EF4444", "#FB7185", "#FBBF24"],
    },
    "sakura": {
        "name": "樱花粉",
        "colors": ["#EC4899", "#F472B6", "#FB7185", "#C084FC", "#FDA4AF"],
    },
    "ocean": {
        "name": "深海蓝",
        "colors": ["#0EA5E9", "#0284C7", "#06B6D4", "#3B82F6", "#0891B2"],
    },
    "graphite": {
        "name": "石墨灰",
        "colors": ["#64748B", "#94A3B8", "#475569", "#7C8DA6", "#52627A"],
    },
    "ember": {
        "name": "熔岩红",
        "colors": ["#DC2626", "#EA580C", "#B91C1C", "#F87171", "#9A3412"],
    },
}

THEME_ORDER = ["aurora", "neon", "forest", "sunset", "sakura", "ocean", "graphite", "ember"]


def get_palette(theme_key):
    """取色板颜色列表，未知主题回落到默认。"""
    return PALETTES.get(theme_key, PALETTES[DEFAULT_THEME])["colors"]


def theme_name(theme_key):
    return PALETTES.get(theme_key, PALETTES[DEFAULT_THEME])["name"]


def is_valid_color(text):
    """校验 #RRGGBB 形式。"""
    if not isinstance(text, str) or len(text) != 7 or not text.startswith("#"):
        return False
    try:
        int(text[1:], 16)
        return True
    except ValueError:
        return False


def _clamp(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))


def hex_to_rgb(color):
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def rgb_to_hex(rgb):
    return "#%02X%02X%02X" % (_clamp(rgb[0]), _clamp(rgb[1]), _clamp(rgb[2]))


def mix(c1, c2, t):
    """线性混色，t=0 返回 c1，t=1 返回 c2。"""
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    return rgb_to_hex((r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t))


def lighten(color, t):
    return mix(color, "#FFFFFF", t)


def darken(color, t):
    return mix(color, "#000000", t)


def luminance(color):
    """相对亮度，用于自动选择黑/白文字。"""
    r, g, b = hex_to_rgb(color)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def text_on(color):
    """返回在该底色上可读的文字色。"""
    return "#101826" if luminance(color) > 0.62 else "#FFFFFF"


# ---------------------------------------------------------------- 界面样式
UI_BG = "#F4F6FB"
UI_CARD = "#FFFFFF"
UI_TEXT = "#101826"
UI_SUB = "#6B7789"
UI_BORDER = "#E3E8F2"
UI_ACCENT = "#4F7DF3"


def app_stylesheet():
    """设置窗口的整体样式表（浅色简约风）。"""
    return """
    QWidget {
        font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
        font-size: 13px;
        color: %(text)s;
    }
    #RootFrame { background: %(bg)s; }
    #TitleBar { background: %(card)s; border-bottom: 1px solid %(border)s; }
    #TitleText { font-size: 15px; font-weight: 600; letter-spacing: 0.5px; }
    #Card {
        background: %(card)s;
        border: 1px solid %(border)s;
        border-radius: 14px;
    }
    #CardTitle { font-size: 12px; color: %(sub)s; font-weight: 600; letter-spacing: 1px; }
    #Hint { color: %(sub)s; font-size: 12px; }
    #Warn { color: #D97706; font-size: 12px; }
    #Danger { color: #DC2626; font-size: 12px; }
    #Ok { color: #059669; font-size: 12px; }
    QLabel#SectionLabel { color: %(sub)s; }
    QPushButton {
        background: #EEF2FA;
        border: 1px solid %(border)s;
        border-radius: 9px;
        padding: 7px 14px;
        color: %(text)s;
    }
    QPushButton:hover { background: #E4EAF7; }
    QPushButton:pressed { background: #DCE3F3; }
    QPushButton:disabled { color: #A9B3C4; background: #F3F5F9; }
    QPushButton#Primary {
        background: %(accent)s;
        border: 1px solid %(accent)s;
        color: #FFFFFF;
        font-weight: 600;
    }
    QPushButton#Primary:hover { background: #3F6DE0; }
    QPushButton#Ghost {
        background: transparent;
        border: 1px solid transparent;
        color: %(sub)s;
        padding: 5px 10px;
    }
    QPushButton#Ghost:hover { background: #EEF2FA; color: %(text)s; }
    QPushButton#WinBtn {
        background: transparent; border: none; border-radius: 6px;
        padding: 6px 12px; color: %(sub)s;
    }
    QPushButton#WinBtn:hover { background: #EEF2FA; color: %(text)s; }
    QPushButton#CloseBtn {
        background: transparent; border: none; border-radius: 6px;
        padding: 6px 12px; color: %(sub)s;
    }
    QPushButton#CloseBtn:hover { background: #EF4444; color: #FFFFFF; }
    QPushButton#Recorder {
        background: #F7F9FD;
        border: 1px dashed #C9D4E8;
        border-radius: 9px;
        padding: 8px 14px;
        font-weight: 600;
        letter-spacing: 0.6px;
    }
    QPushButton#Recorder[recording="true"] {
        border: 1px solid %(accent)s;
        background: #EDF3FF;
        color: %(accent)s;
    }
    QPushButton#RecorderSmall {
        background: #F7F9FD;
        border: 1px dashed #C9D4E8;
        border-radius: 8px;
        padding: 3px 10px;
        font-weight: 600;
        letter-spacing: 0.4px;
    }
    QPushButton#RecorderSmall:hover { background: #F1F5FD; border-color: #A9BCE0; }
    QPushButton#RecorderSmall[recording="true"] {
        border: 1px solid %(accent)s;
        background: #EDF3FF;
        color: %(accent)s;
    }
    QComboBox, QLineEdit, QSpinBox {
        background: #F7F9FD;
        border: 1px solid %(border)s;
        border-radius: 9px;
        padding: 6px 10px;
        min-height: 20px;
        selection-background-color: %(accent)s;
    }
    QComboBox:focus, QLineEdit:focus, QSpinBox:focus { border: 1px solid %(accent)s; }
    QComboBox::drop-down { border: none; width: 22px; }
    QComboBox QAbstractItemView {
        background: #FFFFFF; border: 1px solid %(border)s;
        selection-background-color: #EDF3FF; selection-color: %(text)s;
        outline: none; padding: 4px;
    }
    QSpinBox::up-button, QSpinBox::down-button { width: 18px; border: none; background: transparent; }
    QSlider::groove:horizontal {
        height: 5px; background: #E3E8F2; border-radius: 3px;
    }
    QSlider::sub-page:horizontal { background: %(accent)s; border-radius: 3px; }
    QSlider::handle:horizontal {
        width: 16px; height: 16px; margin: -6px 0;
        border-radius: 8px; background: #FFFFFF; border: 2px solid %(accent)s;
    }
    QTabBar::tab {
        background: transparent;
        border: none;
        padding: 8px 18px;
        margin-right: 4px;
        color: %(sub)s;
        border-radius: 9px;
        font-weight: 500;
    }
    QTabBar::tab:hover { background: #EEF2FA; color: %(text)s; }
    QTabBar::tab:selected {
        background: #E7EFFE;
        color: %(accent)s;
        font-weight: 600;
    }
    QTableWidget {
        background: #FFFFFF;
        border: 1px solid %(border)s;
        border-radius: 12px;
        gridline-color: transparent;
        selection-background-color: #EDF3FF;
        selection-color: %(text)s;
    }
    QTableWidget::item { padding: 4px 6px; }
    QHeaderView::section {
        background: #F7F9FD;
        border: none;
        border-bottom: 1px solid %(border)s;
        padding: 8px 6px;
        color: %(sub)s;
        font-weight: 600;
    }
    QCheckBox::indicator {
        width: 16px; height: 16px;
        border-radius: 5px;
        border: 1px solid #C9D4E8;
        background: #FFFFFF;
    }
    QCheckBox::indicator:checked {
        background: %(accent)s;
        border: 1px solid %(accent)s;
        image: none;
    }
    QScrollBar:vertical {
        background: transparent; width: 10px; margin: 4px;
    }
    QScrollBar::handle:vertical {
        background: #CDD6E6; border-radius: 5px; min-height: 30px;
    }
    QScrollBar::handle:vertical:hover { background: #B6C2D8; }
    QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
    QToolTip {
        background: #1E293B; color: #FFFFFF; border: none;
        padding: 6px 10px; border-radius: 6px; font-size: 12px;
    }
    """ % {
        "text": UI_TEXT,
        "sub": UI_SUB,
        "bg": UI_BG,
        "card": UI_CARD,
        "border": UI_BORDER,
        "accent": UI_ACCENT,
    }
