# -*- coding: utf-8 -*-
"""动作执行层：按键模拟、启动程序、打开网页、系统媒体键。

所有外部调用都包一层异常处理，保证单个动作失败不会让主程序崩溃。
"""

import os
import re
import subprocess
import sys

from . import config as cfgmod
from . import keys as keymod
from . import native

MEDIA_VK = {
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    "mute": 0xAD,
    "play_pause": 0xB3,
    "next": 0xB0,
    "prev": 0xB1,
}

_EXEC_SPLIT = re.compile(r'^"?(.+?\.(?:exe|lnk|bat|cmd|msc|url|vbs|ps1))"?\s*(.*)$', re.IGNORECASE)


def _expand(path):
    return os.path.expandvars(os.path.expanduser(path.strip().strip('"')))


def open_launch_target(value):
    """打开程序 / 文件 / 文件夹，支持带参数。"""
    raw = (value or "").strip()
    if not raw:
        return False, "目标为空"
    path = _expand(raw)

    # 已存在的路径或协议（如 ms-settings:、https://）直接交给系统 shell
    if os.path.exists(path):
        os.startfile(path)  # noqa: SLF001 - Windows 专用
        return True, ""

    m = _EXEC_SPLIT.match(path)
    if m:
        exe = m.group(1).strip().strip('"')
        args = m.group(2).strip()
        if os.path.exists(exe):
            cmd = [exe] + ([args] if args else [])
            subprocess.Popen(cmd, close_fds=True)
            return True, ""
        # exe 在 PATH 中
        if os.path.sep not in exe:
            subprocess.Popen([exe] + ([args] if args else []), close_fds=True)
            return True, ""

    if "://" in path or path.lower().startswith(("shell:", "ms-", "mailto:", "file:")):
        os.startfile(path)  # noqa: SLF001
        return True, ""

    return False, "找不到目标：%s" % raw


def open_url(url):
    raw = (url or "").strip()
    if not raw:
        return False, "网址为空"
    if "://" not in raw:
        raw = "https://" + raw
    os.startfile(raw)  # noqa: SLF001
    return True, ""


def send_keys(label):
    """发送按键组合，如 'Ctrl+Shift+A'。"""
    mods, vk = keymod.parse_label(label)
    if vk is None:
        return False, "无法识别按键：%s" % (label or "(空)")
    native.send_combo(vk, mods or [])
    return True, ""


def send_media(value):
    if value == "lock":
        native.lock_workstation()
        return True, ""
    vk = MEDIA_VK.get(value)
    if vk is None:
        return False, "未知媒体动作：%s" % value
    native.send_combo(vk, [])
    return True, ""


def execute(action):
    """执行一个动作，返回 (成功?, 错误说明)。"""
    if not isinstance(action, dict):
        return False, "动作配置无效"
    atype = action.get("type")
    value = action.get("value")
    try:
        if atype == cfgmod.ACTION_KEYS:
            return send_keys(value)
        if atype == cfgmod.ACTION_LAUNCH:
            return open_launch_target(value)
        if atype == cfgmod.ACTION_URL:
            return open_url(value)
        if atype == cfgmod.ACTION_MEDIA:
            return send_media(value)
        return False, "未知动作类型：%s" % atype
    except Exception as exc:  # 外部调用可能抛各种异常
        return False, "%s: %s" % (type(exc).__name__, exc)


def describe(action):
    """动作的人类可读描述，用于日志与提示。"""
    if not isinstance(action, dict):
        return ""
    atype = action.get("type")
    value = action.get("value") or ""
    if atype == cfgmod.ACTION_KEYS:
        return value
    if atype == cfgmod.ACTION_MEDIA:
        return dict(cfgmod.MEDIA_ACTIONS).get(value, value)
    return value


def startup_command():
    """开机自启时写入注册表的目标命令行。"""
    if getattr(sys, "frozen", False):
        return '"%s"' % sys.executable
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return '"%s" "%s"' % (sys.executable, script)
