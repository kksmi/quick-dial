# -*- coding: utf-8 -*-
"""追踪钩子层真实事件流：确认 Alt 抬起事件有没有到达、有没有被吞。"""

import os
import sys
import time

os.environ["QUICKDIAL_ALLOW_INJECTED"] = "1"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import ctypes  # noqa: E402

from app import keys as keymod  # noqa: E402
from app import native  # noqa: E402

ALT, W = 0x12, 0x57
events = []


def on_key(vk, down):
    # 完全模拟 controller 的策略：转盘打开时吞非修饰键，修饰键透传
    swallow = False
    if not down:
        swallow = False
    elif vk != ALT:
        swallow = True
    if down and vk == W:
        swallow = True
    events.append((vk, down, swallow))
    return swallow


def phys():
    u = ctypes.windll.user32
    return bool(u.GetAsyncKeyState(ALT) & 0x8000), bool(u.GetAsyncKeyState(W) & 0x8000)


def main():
    hooks = native.InputHooks(on_key, lambda d: False)
    if not hooks.start():
        print("钩子启动失败")
        return 1
    time.sleep(0.3)

    print("起始物理状态 alt,w =", phys())
    native._send_key(ALT, False)
    time.sleep(0.15)
    print("Alt 按下后 =", phys())
    native._send_key(W, False)
    time.sleep(0.25)
    print("W 按下后   =", phys())

    print("--> 先松 Alt")
    native._send_key(ALT, True)
    time.sleep(0.2)
    print("Alt 松开后 =", phys())

    print("--> 再松 W")
    native._send_key(W, True)
    time.sleep(0.3)
    print("W 松开后   =", phys())

    print("\n钩子收到的事件（vk, 按下, 是否吞掉）:")
    for e in events:
        print("   %s %-5s %s" % (keymod.vk_to_name(e[0]), "down" if e[1] else "up", "吞" if e[2] else "透传"))

    # 再看纯透传模式下物理状态是否正常
    hooks.stop()
    time.sleep(0.2)
    print("\n钩子卸载后物理状态 =", phys())
    native._send_key(ALT, False)
    time.sleep(0.1)
    native._send_key(ALT, True)
    time.sleep(0.1)
    print("卸载后手动按放 Alt =", phys())
    return 0


if __name__ == "__main__":
    sys.exit(main())
