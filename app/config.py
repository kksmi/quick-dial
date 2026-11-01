# -*- coding: utf-8 -*-
"""配置模型：轮盘配置的默认值、校验、读写与导入导出。

单一事实来源：所有默认值集中在此，UI 与转盘渲染都从这里取。
"""

import json
import os
import uuid

from . import keys as keymod
from . import theme

MIN_SEGMENTS = 2
MAX_SEGMENTS = 10

DIAMETER_MIN = 180
DIAMETER_MAX = 760
DIAMETER_DEFAULT = 360

POSITION_CURSOR = "cursor"
POSITION_CENTER = "center"

SELECT_MOUSE = "mouse"
SELECT_WHEEL = "wheel"

ACTION_KEYS = "keys"
ACTION_LAUNCH = "launch"
ACTION_URL = "url"
ACTION_MEDIA = "media"

ACTION_LABELS = [
    (ACTION_KEYS, "发送按键组合"),
    (ACTION_LAUNCH, "打开程序 / 文件"),
    (ACTION_URL, "打开网页"),
    (ACTION_MEDIA, "系统媒体键"),
]

# 媒体键动作的可选值
MEDIA_ACTIONS = [
    ("volume_up", "音量 +"),
    ("volume_down", "音量 -"),
    ("mute", "静音"),
    ("play_pause", "播放 / 暂停"),
    ("next", "下一曲"),
    ("prev", "上一曲"),
    ("lock", "锁定屏幕"),
]

APP_NAME = "QuickDial"
CONFIG_DIR_NAME = "QuickDial"
CONFIG_FILE_NAME = "config.json"


def _new_id():
    return uuid.uuid4().hex[:8]


def default_segments(theme_key=theme.DEFAULT_THEME, count=8):
    """按主题色板生成默认扇区。"""
    palette = theme.get_palette(theme_key)
    preset = [
        ("复制", ACTION_KEYS, "Ctrl+C"),
        ("粘贴", ACTION_KEYS, "Ctrl+V"),
        ("剪切", ACTION_KEYS, "Ctrl+X"),
        ("撤销", ACTION_KEYS, "Ctrl+Z"),
        ("重做", ACTION_KEYS, "Ctrl+Y"),
        ("全选", ACTION_KEYS, "Ctrl+A"),
        ("保存", ACTION_KEYS, "Ctrl+S"),
        ("截图", ACTION_KEYS, "Win+Shift+S"),
        ("关闭窗口", ACTION_KEYS, "Alt+F4"),
        ("打开设置", ACTION_LAUNCH, "explorer.exe ms-settings:"),
    ]
    out = []
    for i in range(count):
        name, atype, value = preset[i % len(preset)]
        out.append(
            {
                "name": name,
                "color": palette[i % len(palette)],
                "action": {"type": atype, "value": value},
            }
        )
    return out


def make_wheel(name="主轮盘", hotkey_label="Alt+W", theme_key=None, count=8):
    theme_key = theme_key or theme.DEFAULT_THEME
    mods, vk = keymod.parse_label(hotkey_label)
    if vk is None:
        mods, vk = ["alt"], 0x57
    return {
        "id": _new_id(),
        "name": name,
        "hotkey": {
            "vk": vk,
            "mods": mods,
            "label": keymod.make_label(mods, vk),
        },
        "position_mode": POSITION_CURSOR,
        "diameter": DIAMETER_DEFAULT,
        "select_mode": SELECT_MOUSE,
        "sensitivity": 6,
        "theme": theme_key,
        "accent": theme.get_palette(theme_key)[0],
        "show_hint": True,
        "segments": default_segments(theme_key, count),
    }


def default_config():
    return {
        "version": 1,
        "launch_at_startup": False,
        "wheels": [make_wheel()],
    }


# ---------------------------------------------------------------- 校验
def _as_int(value, fallback, lo, hi):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(lo, min(hi, v))


def _as_str(value, fallback=""):
    if isinstance(value, str):
        return value
    if value is None:
        return fallback
    return str(value)


def _normalize_action(raw):
    """容错解析动作字段。"""
    if not isinstance(raw, dict):
        raw = {}
    atype = _as_str(raw.get("type"), ACTION_KEYS)
    if atype not in (ACTION_KEYS, ACTION_LAUNCH, ACTION_URL, ACTION_MEDIA):
        atype = ACTION_KEYS
    value = _as_str(raw.get("value"), "")
    if atype == ACTION_MEDIA and value not in dict(MEDIA_ACTIONS):
        value = MEDIA_ACTIONS[0][0]
    return {"type": atype, "value": value}


def normalize_wheel(raw):
    """把任意输入（含损坏的 JSON）整理成合法 wheel 配置。"""
    if not isinstance(raw, dict):
        raw = {}
    base = make_wheel()
    wheel = dict(base)
    wheel["id"] = _as_str(raw.get("id"), "") or _new_id()
    wheel["name"] = _as_str(raw.get("name"), "轮盘").strip() or "轮盘"

    hk = raw.get("hotkey")
    if isinstance(hk, dict):
        vk = _as_int(hk.get("vk"), 0x57, 0x01, 0xFE)
        mods_raw = hk.get("mods")
        if isinstance(mods_raw, list):
            mods = [m for m in mods_raw if m in keymod.MOD_ORDER]
        else:
            mods, _ = keymod.parse_label(_as_str(hk.get("label"), ""))
            mods = mods or []
        label = _as_str(hk.get("label"), "") or keymod.make_label(mods, vk)
        wheel["hotkey"] = {"vk": vk, "mods": mods, "label": label}
    else:
        mods, vk = keymod.parse_label(_as_str(raw.get("hotkey"), ""))
        if vk is not None:
            wheel["hotkey"] = {
                "vk": vk,
                "mods": mods,
                "label": keymod.make_label(mods, vk),
            }

    pm = _as_str(raw.get("position_mode"), POSITION_CURSOR)
    wheel["position_mode"] = pm if pm in (POSITION_CURSOR, POSITION_CENTER) else POSITION_CURSOR

    sm = _as_str(raw.get("select_mode"), SELECT_MOUSE)
    wheel["select_mode"] = sm if sm in (SELECT_MOUSE, SELECT_WHEEL) else SELECT_MOUSE

    wheel["diameter"] = _as_int(raw.get("diameter"), DIAMETER_DEFAULT, DIAMETER_MIN, DIAMETER_MAX)
    wheel["sensitivity"] = _as_int(raw.get("sensitivity"), 6, 1, 10)
    wheel["show_hint"] = bool(raw.get("show_hint", True))

    theme_key = _as_str(raw.get("theme"), theme.DEFAULT_THEME)
    if theme_key not in theme.PALETTES:
        theme_key = theme.DEFAULT_THEME
    wheel["theme"] = theme_key

    accent = _as_str(raw.get("accent"), "")
    if not theme.is_valid_color(accent):
        accent = theme.get_palette(theme_key)[0]
    wheel["accent"] = accent

    segs_raw = raw.get("segments")
    segs = []
    if isinstance(segs_raw, list):
        for s in segs_raw[:MAX_SEGMENTS]:
            if not isinstance(s, dict):
                continue
            color = _as_str(s.get("color"), "")
            if not theme.is_valid_color(color):
                color = theme.get_palette(theme_key)[len(segs) % 5]
            segs.append(
                {
                    "name": _as_str(s.get("name"), "项目").strip() or "项目",
                    "color": color.upper(),
                    "action": _normalize_action(s.get("action")),
                }
            )
    if len(segs) < MIN_SEGMENTS:
        segs = default_segments(theme_key, max(MIN_SEGMENTS, len(segs)))
    wheel["segments"] = segs
    return wheel


def normalize_config(raw):
    if not isinstance(raw, dict):
        raw = {}
    wheels_raw = raw.get("wheels")
    wheels = []
    if isinstance(wheels_raw, list):
        for w in wheels_raw:
            wheels.append(normalize_wheel(w))
    if not wheels:
        wheels = [normalize_wheel({})]
    return {
        "version": 1,
        "launch_at_startup": bool(raw.get("launch_at_startup", False)),
        "wheels": wheels,
    }


def resize_segments(wheel, count):
    """把扇区数量调整为目标值，保留已有内容。"""
    count = _as_int(count, len(wheel["segments"]), MIN_SEGMENTS, MAX_SEGMENTS)
    segs = wheel["segments"]
    palette = theme.get_palette(wheel.get("theme", theme.DEFAULT_THEME))
    while len(segs) > count:
        segs.pop()
    idx = len(segs)
    while len(segs) < count:
        segs.append(
            {
                "name": "项目 %d" % (idx + 1),
                "color": palette[idx % len(palette)],
                "action": {"type": ACTION_KEYS, "value": ""},
            }
        )
        idx += 1
    return wheel


# ---------------------------------------------------------------- 存取
def config_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, CONFIG_DIR_NAME)


def config_path():
    return os.path.join(config_dir(), CONFIG_FILE_NAME)


def load_config(path=None):
    """读取配置；文件不存在或损坏时返回默认配置（不抛异常）。"""
    path = path or config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return normalize_config(data)
    except (OSError, ValueError):
        return default_config()


def save_config(cfg, path=None):
    """原子写入，避免写一半断电导致配置损坏。"""
    path = path or config_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def export_config(cfg, path):
    return save_config(normalize_config(cfg), path)


def import_config(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return normalize_config(data)
