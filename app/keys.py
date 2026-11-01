# -*- coding: utf-8 -*-
"""键盘映射层：Qt 键码 <-> Windows 虚拟键码(VK) <-> 可读标签。

集中维护一张表，避免在其它模块里散落 VK 魔数导致不一致。
"""

from PySide6.QtCore import Qt

# ---------------------------------------------------------------- 修饰键
MOD_CTRL = "ctrl"
MOD_ALT = "alt"
MOD_SHIFT = "shift"
MOD_WIN = "win"

# 生成标签时的固定顺序（与 Windows 习惯一致）
# Win 组合习惯写作 "Win+Shift+S"，其余按 Ctrl/Alt/Shift 顺序
MOD_ORDER = [MOD_WIN, MOD_CTRL, MOD_ALT, MOD_SHIFT]
MOD_LABEL = {MOD_CTRL: "Ctrl", MOD_ALT: "Alt", MOD_SHIFT: "Shift", MOD_WIN: "Win"}
MOD_VK = {MOD_CTRL: 0x11, MOD_ALT: 0x12, MOD_SHIFT: 0x10}

# ---------------------------------------------------------------- VK 名称表
# vk -> 可读名（解析标签时反向使用）
_VK_NAME = {}
_NAME_VK = {}


def _reg(vk, name, *aliases):
    _VK_NAME[vk] = name
    _NAME_VK[name.lower()] = vk
    for a in aliases:
        _NAME_VK[a.lower()] = vk


# 字母
for _i in range(26):
    _reg(0x41 + _i, chr(0x41 + _i))
# 主键盘数字
for _i in range(10):
    _reg(0x30 + _i, str(_i))
# 功能键
for _i in range(24):
    _reg(0x70 + _i, "F%d" % (_i + 1))
# 小键盘
for _i in range(10):
    _reg(0x60 + _i, "Num%d" % _i, "Numpad%d" % _i)
# 常用控制键
_reg(0x08, "Backspace", "Back")
_reg(0x09, "Tab")
_reg(0x0D, "Enter", "Return")
_reg(0x1B, "Esc", "Escape")
_reg(0x20, "Space", "Spacebar")
_reg(0x21, "PageUp", "PgUp")
_reg(0x22, "PageDown", "PgDn")
_reg(0x23, "End")
_reg(0x24, "Home")
_reg(0x25, "Left")
_reg(0x26, "Up")
_reg(0x27, "Right")
_reg(0x28, "Down")
_reg(0x2C, "PrintScreen", "PrtSc")
_reg(0x2D, "Insert", "Ins")
_reg(0x2E, "Delete", "Del")
_reg(0x13, "Pause", "Break")
_reg(0x14, "CapsLock")
_reg(0x90, "NumLock")
_reg(0x91, "ScrollLock")
_reg(0x5D, "Menu", "Apps")
# 小键盘运算键
_reg(0x6A, "Num*", "NumpadMultiply")
_reg(0x6B, "Num+", "NumpadAdd")
_reg(0x6C, "NumSep")
_reg(0x6D, "Num-", "NumpadSubtract")
_reg(0x6E, "Num.", "NumpadDecimal")
_reg(0x6F, "Num/", "NumpadDivide")
# 符号键（OEM）
_reg(0xC0, "`", "Backquote", "~")
_reg(0xBD, "-", "Minus")
_reg(0xBB, "=", "Equal", "Plus")
_reg(0xDB, "[", "BracketLeft")
_reg(0xDD, "]", "BracketRight")
_reg(0xDC, "\\", "Backslash")
_reg(0xBA, ";", "Semicolon")
_reg(0xDE, "'", "Quote", "Apostrophe")
_reg(0xBC, ",", "Comma")
_reg(0xBE, ".", "Period")
_reg(0xBF, "/", "Slash")
# 媒体与系统键
_reg(0xAD, "Mute", "VolumeMute")
_reg(0xAE, "VolumeDown")
_reg(0xAF, "VolumeUp")
_reg(0xB0, "MediaNext", "NextTrack")
_reg(0xB1, "MediaPrev", "PrevTrack")
_reg(0xB2, "MediaStop")
_reg(0xB3, "MediaPlay", "PlayPause")
_reg(0xA6, "BrowserBack")
_reg(0xA7, "BrowserForward")
_reg(0xA8, "BrowserRefresh")
_reg(0xA9, "BrowserStop")
_reg(0xAA, "BrowserSearch")
_reg(0xAB, "BrowserFavorites")
_reg(0xAC, "BrowserHome")
_reg(0xB4, "LaunchMail")
_reg(0xB5, "LaunchMedia")

# ------------------------------------------------- Qt 键码 -> VK（非 ASCII 段）
QT_KEY_TO_VK = {}


def _q(qt_key_name, vk):
    val = getattr(Qt, qt_key_name, None)
    if val is not None:
        QT_KEY_TO_VK[int(val)] = vk


_q("Key_Escape", 0x1B)
_q("Key_Tab", 0x09)
_q("Key_Backtab", 0x09)
_q("Key_Backspace", 0x08)
_q("Key_Return", 0x0D)
_q("Key_Enter", 0x0D)
_q("Key_Insert", 0x2D)
_q("Key_Delete", 0x2E)
_q("Key_Pause", 0x13)
_q("Key_Print", 0x2C)
_q("Key_SysReq", 0x2C)
_q("Key_Clear", 0x0C)
_q("Key_Home", 0x24)
_q("Key_End", 0x23)
_q("Key_Left", 0x25)
_q("Key_Up", 0x26)
_q("Key_Right", 0x27)
_q("Key_Down", 0x28)
_q("Key_PageUp", 0x21)
_q("Key_PageDown", 0x22)
_q("Key_CapsLock", 0x14)
_q("Key_NumLock", 0x90)
_q("Key_ScrollLock", 0x91)
_q("Key_Menu", 0x5D)
for _i in range(1, 25):
    _q("Key_F%d" % _i, 0x70 + _i - 1)
for _i in range(10):
    _q("Key_%d" % _i, 0x30 + _i)
# 媒体键（Qt 能捕获到的部分）
_q("Key_VolumeDown", 0xAE)
_q("Key_VolumeMute", 0xAD)
_q("Key_VolumeUp", 0xAF)
_q("Key_MediaNext", 0xB0)
_q("Key_MediaPrevious", 0xB1)
_q("Key_MediaStop", 0xB2)
_q("Key_MediaPlay", 0xB3)
_q("Key_MediaPause", 0xB3)
_q("Key_MediaTogglePlayPause", 0xB3)
# 小键盘
for _i in range(10):
    _q("Key_%d" % _i, 0x60 + _i)  # 覆盖为小键盘需运行时按 KeypadModifier 判断
QT_KP_TO_VK = {}
for _i in range(10):
    QT_KP_TO_VK[0x30 + _i] = 0x60 + _i

# 符号：Qt 用 Unicode 码位表示，与 VK 不同，需单独映射
QT_CHAR_TO_VK = {
    0x60: 0xC0, 0x7E: 0xC0,
    0x2D: 0xBD, 0x5F: 0xBD,
    0x3D: 0xBB, 0x2B: 0xBB,
    0x5B: 0xDB, 0x7B: 0xDB,
    0x5D: 0xDD, 0x7D: 0xDD,
    0x5C: 0xDC, 0x7C: 0xDC,
    0x3B: 0xBA, 0x3A: 0xBA,
    0x27: 0xDE, 0x22: 0xDE,
    0x2C: 0xBC, 0x3C: 0xBC,
    0x2E: 0xBE, 0x3E: 0xBE,
    0x2F: 0xBF, 0x3F: 0xBF,
}


def vk_to_name(vk):
    """VK -> 显示名；未知键返回 '0xXX'。"""
    return _VK_NAME.get(int(vk), "0x%02X" % int(vk))


def vk_from_name(name):
    """显示名 -> VK；支持别名与大小写混写。"""
    if not name:
        return None
    key = name.strip().lower()
    if key in _NAME_VK:
        return _NAME_VK[key]
    # 形如 "0x51"
    if key.startswith("0x"):
        try:
            return int(key, 16)
        except ValueError:
            return None
    return None


# 低层键盘钩子上报的是"具体到左右"的虚拟键码：
#   LShift=0xA0 RShift=0xA1 LCtrl=0xA2 RCtrl=0xA3 LAlt=0xA4 RAlt=0xA5 LWin=0x5B RWin=0x5C
# 通用码（0x10/0x11/0x12）只在部分场景出现，两边都要认。
_SIDE_MODIFIER_VK = {0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}
_MODIFIER_VK = {0x10, 0x11, 0x12, 0x5B, 0x5C} | _SIDE_MODIFIER_VK

# 左右修饰键 -> 通用码，便于统一比较
_SIDE_TO_GENERIC = {
    0xA0: 0x10,
    0xA1: 0x10,
    0xA2: 0x11,
    0xA3: 0x11,
    0xA4: 0x12,
    0xA5: 0x12,
}


def normalize_vk(vk):
    """把"左侧 Alt(0xA4)"这类具体码归一化为通用码(0x12)。

    钩子回调、热键匹配、松手判断都必须先归一化，否则会出现
    "按下是 Alt、抬起是 LAlt"对不上号的情况。
    """
    return _SIDE_TO_GENERIC.get(int(vk), int(vk))


def is_modifier_vk(vk):
    """含左右两侧的修饰键判断（钩子上报的是具体侧）。"""
    return int(vk) in _MODIFIER_VK


def make_label(mods, vk):
    """按固定顺序拼出可读标签，如 Alt+Q。"""
    parts = [MOD_LABEL[m] for m in MOD_ORDER if m in mods]
    parts.append(vk_to_name(vk))
    return "+".join(parts)


def parse_label(label):
    """标签 -> (mods 列表, vk)。

    接受任意顺序、大小写不敏感，无法解析时返回 (None, None)。
    """
    if not label:
        return None, None
    parts = [p for p in str(label).split("+") if p != ""]
    if not parts:
        return None, None
    # 末尾空字符串表示主键就是 '+' 本身
    if str(label).endswith("+"):
        parts.append("=")
    mods = []
    vk = None
    for i, raw in enumerate(parts):
        token = raw.strip().lower()
        if token in ("ctrl", "control"):
            mods.append(MOD_CTRL)
        elif token in ("alt", "menu"):
            mods.append(MOD_ALT)
        elif token in ("shift",):
            mods.append(MOD_SHIFT)
        elif token in ("win", "meta", "cmd", "super"):
            mods.append(MOD_WIN)
        else:
            vk = vk_from_name(raw)
    if vk is None:
        return None, None
    if is_modifier_vk(vk):
        return None, None
    return mods, vk


def _qv(value):
    """PySide6 的 Flag 枚举不能直接 int()，统一取 .value。"""
    return int(getattr(value, "value", value))


def label_from_seq(seq):
    """QKeySequence -> 标签；无法识别返回空串。"""
    if seq is None or seq.isEmpty():
        return ""
    combined = seq[0].toCombined()
    key = combined & 0x01FFFFFF
    qt_mods = combined & 0xFE000000
    return label_from_qt(key, qt_mods)


def label_from_qt(qt_key, qt_mods):
    """Qt 的 (键码, 修饰位) -> 可读标签。"""
    vk = vk_from_qt(qt_key, qt_mods)
    if vk is None:
        return ""
    mods = qt_mods_to_mods(qt_mods)
    return make_label(mods, vk)


def qt_mods_to_mods(qt_mods):
    mods = []
    flags = _qv(qt_mods)
    if flags & _qv(Qt.ControlModifier):
        mods.append(MOD_CTRL)
    if flags & _qv(Qt.AltModifier):
        mods.append(MOD_ALT)
    if flags & _qv(Qt.ShiftModifier):
        mods.append(MOD_SHIFT)
    if flags & _qv(Qt.MetaModifier):
        mods.append(MOD_WIN)
    return mods


def vk_from_qt(qt_key, qt_mods=0):
    """Qt 键码 -> VK。无法映射时返回 None。"""
    key = int(qt_key)
    # 小键盘数字
    if _qv(qt_mods) & _qv(Qt.KeypadModifier) and key in QT_KP_TO_VK:
        return QT_KP_TO_VK[key]
    if key in QT_KEY_TO_VK:
        return QT_KEY_TO_VK[key]
    # ASCII 字母/数字
    if 0x41 <= key <= 0x5A:
        return key
    if 0x30 <= key <= 0x39:
        return key
    # 符号（Qt 用 Unicode 码位）
    if key in QT_CHAR_TO_VK:
        return QT_CHAR_TO_VK[key]
    if key == 0x20:
        return 0x20
    return None


def mods_to_mask(mods):
    """mods 列表 -> (ctrl, alt, shift, win) 布尔组，便于比较。"""
    return (MOD_CTRL in mods, MOD_ALT in mods, MOD_SHIFT in mods, MOD_WIN in mods)


# ------------------------------------------------- Windows 系统保留组合
# 只做提示用途：命中后仍允许保存，但 UI 会警告
SYSTEM_RESERVED = [
    (["win"], 0x4C, "Win+L 锁定屏幕"),
    (["win"], 0x44, "Win+D 显示桌面"),
    (["win"], 0x45, "Win+E 打开资源管理器"),
    (["win"], 0x52, "Win+R 运行"),
    (["win"], 0x53, "Win+S 搜索"),
    (["win"], 0x49, "Win+I 设置"),
    (["win"], 0x41, "Win+A 操作中心"),
    (["win"], 0x50, "Win+P 投影"),
    (["win"], 0x58, "Win+X 快捷菜单"),
    (["win"], 0x56, "Win+V 剪贴板历史"),
    (["win"], 0x4B, "Win+K 连接设备"),
    (["win"], 0x4D, "Win+M 最小化全部"),
    (["win"], 0x2E, "Win+Delete 文件资源管理器"),
    (["win"], 0x20, "Win+Space 输入法切换"),
    (["win", "shift"], 0x53, "Win+Shift+S 截图"),
    (["win", "shift"], 0x4C, "Win+Shift+L"),
    (["win", "ctrl"], 0x44, "Win+Ctrl+D 虚拟桌面"),
    (["win", "ctrl"], 0x46, "Win+Ctrl+F"),
    (["ctrl", "alt"], 0x2E, "Ctrl+Alt+Del 安全选项（系统独占）"),
    (["ctrl", "shift"], 0x1B, "Ctrl+Shift+Esc 任务管理器"),
    (["alt"], 0x09, "Alt+Tab 切换窗口"),
    (["alt"], 0x73, "Alt+F4 关闭窗口"),
    (["alt"], 0x20, "Alt+Space 窗口菜单"),
    (["ctrl"], 0x1B, "Ctrl+Esc 开始菜单"),
    (["alt", "shift"], 0x09, "Alt+Shift+Tab 反向切换窗口"),
]


def check_reserved(mods, vk):
    """命中系统保留组合时返回说明文本，否则 None。"""
    want = mods_to_mask(mods)
    for r_mods, r_vk, desc in SYSTEM_RESERVED:
        if int(vk) == r_vk and mods_to_mask(r_mods) == want:
            return desc
    return None
