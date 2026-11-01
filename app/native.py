# -*- coding: utf-8 -*-
"""Windows 原生交互：全局低层钩子、按键注入、光标位置、热键占用探测。

为什么不用第三方库：
- 低层钩子能同时拿到"按下"和"松开"，这是"松开热键执行动作"的前提；
- 自己实现可以精确控制何时吞掉事件（转盘打开时不把按键透传给前台程序）。
"""

import ctypes
import os
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEWHEEL = 0x020A
WM_QUIT = 0x0012

LLKHF_INJECTED = 0x10
LLMHF_INJECTED = 0x01

# 仅用于自动化测试：允许钩子响应模拟注入的按键。
# 生产环境保持关闭，否则程序自己发出的按键可能反过来触发自己。
_ALLOW_INJECTED = os.environ.get("QUICKDIAL_ALLOW_INJECTED") == "1"

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C

KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
ERROR_HOTKEY_ALREADY_REGISTERED = 1409


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def get_cursor_pos():
    """当前光标屏幕坐标 (x, y)。"""
    pt = POINT()
    if user32.GetCursorPos(ctypes.byref(pt)):
        return pt.x, pt.y
    return 0, 0


def modifier_state():
    """返回 (ctrl, alt, shift, win) 当前是否按下。"""
    def down(vk):
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)

    return (
        down(VK_CONTROL),
        down(VK_MENU),
        down(VK_SHIFT),
        down(VK_LWIN) or down(VK_RWIN),
    )


def probe_hotkey(vk, mods):
    """探测组合键是否已被系统或其它程序占用。

    返回 (free, reason)。使用临时 RegisterHotKey 探测，成功即注销。
    注意：低层钩子优先级高于 RegisterHotKey，所以"被占用"不代表我们收不到，
    仅作为冲突提示。
    """
    mask = 0
    if "alt" in mods:
        mask |= MOD_ALT
    if "ctrl" in mods:
        mask |= MOD_CONTROL
    if "shift" in mods:
        mask |= MOD_SHIFT
    if "win" in mods:
        mask |= MOD_WIN
    hotkey_id = 0xBEEF
    ctypes.set_last_error(0)
    ok = user32.RegisterHotKey(None, hotkey_id, mask, int(vk))
    if ok:
        user32.UnregisterHotKey(None, hotkey_id)
        return True, ""
    err = ctypes.get_last_error()
    if err == ERROR_HOTKEY_ALREADY_REGISTERED:
        return False, "该组合键已被其它程序注册"
    return False, "系统拒绝该组合键（错误码 %d）" % err


def _send_key(vk, up=False):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki = KEYBDINPUT(
        wVk=int(vk),
        wScan=0,
        dwFlags=KEYEVENTF_KEYUP if up else 0,
        time=0,
        dwExtraInfo=0,
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


# 修饰键按下/释放顺序，Ctrl 先按、最后松开，避免组合键被前台程序误解
_MOD_VK_SEQ = [("ctrl", VK_CONTROL), ("alt", VK_MENU), ("shift", VK_SHIFT), ("win", VK_LWIN)]


def send_combo(vk, mods):
    """模拟发送一次组合键。"""
    pressed = []
    for name, mvk in _MOD_VK_SEQ:
        if name in mods:
            _send_key(mvk, False)
            pressed.append(mvk)
    _send_key(vk, False)
    _send_key(vk, True)
    for mvk in reversed(pressed):
        _send_key(mvk, True)


class InputHooks:
    """在独立线程里安装键盘/鼠标低层钩子。

    回调会在这个后台线程中执行，回调实现必须快速返回，
    且不要直接操作 Qt 控件（用信号投递回主线程）。
    """

    def __init__(self, on_key, on_wheel):
        # on_key(vk, is_down) -> bool 是否吞掉
        # on_wheel(delta) -> bool 是否吞掉
        self._on_key = on_key
        self._on_wheel = on_wheel
        self._thread = None
        self._thread_id = 0
        self._kb_hook = None
        self._ms_hook = None
        self._ready = threading.Event()
        self._alive = False
        # 必须持有 CFUNCTYPE 引用，否则会被 GC 掉导致钩子回调崩溃
        self._kb_proc = HOOKPROC(self._kb_callback)
        self._ms_proc = HOOKPROC(self._ms_callback)

    # ---------------------------------------------------------- 生命周期
    def start(self):
        if self._thread and self._thread.is_alive():
            return True
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="InputHooks", daemon=True)
        self._thread.start()
        self._ready.wait(3.0)
        return self._alive

    def stop(self):
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(2.0)
        self._thread = None
        self._alive = False

    @property
    def alive(self):
        return self._alive

    def _run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        hmod = kernel32.GetModuleHandleW(None)
        self._kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, hmod, 0)
        self._ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._ms_proc, hmod, 0)
        self._alive = bool(self._kb_hook)
        self._ready.set()
        if not self._alive:
            return

        msg = wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._kb_hook:
            user32.UnhookWindowsHookEx(self._kb_hook)
        if self._ms_hook:
            user32.UnhookWindowsHookEx(self._ms_hook)
        self._kb_hook = None
        self._ms_hook = None

    # ---------------------------------------------------------- 回调
    def _kb_callback(self, n_code, w_param, l_param):
        if n_code == HC_ACTION:
            try:
                kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                # 忽略我们自己注入的按键，否则发送动作会再次触发热键
                if _ALLOW_INJECTED or not (kb.flags & LLKHF_INJECTED):
                    is_down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    if self._on_key(int(kb.vkCode), is_down):
                        return 1
            except Exception:
                pass
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _ms_callback(self, n_code, w_param, l_param):
        if n_code == HC_ACTION and w_param == WM_MOUSEWHEEL:
            try:
                ms = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if _ALLOW_INJECTED or not (ms.flags & LLMHF_INJECTED):
                    delta = ctypes.c_short((ms.mouseData >> 16) & 0xFFFF).value
                    if self._on_wheel(int(delta)):
                        return 1
            except Exception:
                pass
        return user32.CallNextHookEx(None, n_code, w_param, l_param)


def lock_workstation():
    """Win+L 等价操作，用于媒体键动作里的"锁定屏幕"。"""
    return bool(user32.LockWorkStation())
