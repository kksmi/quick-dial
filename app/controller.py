# -*- coding: utf-8 -*-
"""主控制器：把全局钩子、转盘窗口、配置与动作执行串起来。"""

import os
import sys
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import actions, config as cfgmod, keys as keymod, native, theme
from .radial import RadialWheel

# 热键修饰键（配置里的字符串）-> 归一化后的通用 VK
_MOD_STR_TO_VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B}


def make_app_icon(size=64):
    """程序图标：同心的彩色圆环，与转盘视觉一致。"""
    pm = QPixmap(size, size)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    colors = ["#3B82F6", "#22D3EE", "#6366F1", "#14B8A6", "#0EA5E9", "#22D3EE"]
    n = len(colors)
    r = size * 0.46
    cx = cy = size / 2.0
    from PySide6.QtCore import QRectF

    for i, c in enumerate(colors):
        a0 = 90 - i * (360.0 / n)
        p.setBrush(QColor(c))
        p.setPen(QColor(255, 255, 255, 40))
        p.drawPie(QRectF(cx - r, cy - r, r * 2, r * 2), int(a0 * 16), int(-(360.0 / n) * 16 + 24))
    p.setBrush(QColor(12, 17, 27))
    p.setPen(QColor(255, 255, 255, 40))
    p.drawEllipse(QRectF(cx - r * 0.34, cy - r * 0.34, r * 0.68, r * 0.68))
    p.end()
    return QIcon(pm)


class Controller(QObject):
    hotkey_pressed = Signal(int)
    hotkey_released = Signal()
    wheel_scrolled = Signal(int)

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.cfg = cfgmod.load_config()
        self.wheel = RadialWheel()
        self.hooks = native.InputHooks(self._on_key_raw, self._on_wheel_raw)
        self.settings = None
        self.tray = None
        self.enabled = True
        self._record_paused = False
        self._active_wheel = -1
        # 钩子线程本地维护的"热键已按下"状态，主线程不参与判断
        self._armed = False
        self._armed_vk = 0
        self._armed_mods = frozenset()
        self._armed_ts = 0.0
        self._pending_action = None
        self._pending_wheel_cfg = None
        self._cancel_pending = False
        self._wait_ms = 0
        self._wait_limit = 1200

        self.hotkey_pressed.connect(self._open_wheel)
        self.hotkey_released.connect(self._on_release)
        self.wheel_scrolled.connect(self._on_scroll)
        self.wheel.segmentClicked.connect(self._on_segment_clicked)
        self.wheel.dismissRequested.connect(self._on_dismiss)

        # 光标轮询：16ms 一帧，只在转盘打开时工作
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(16)
        self._cursor_timer.timeout.connect(self._poll_cursor)

        # 等待修饰键释放后再执行，避免 Alt+Q 呼出时执行 Ctrl+C 变成 Ctrl+Alt+C
        self._wait_timer = QTimer(self)
        self._wait_timer.setInterval(20)
        self._wait_timer.timeout.connect(self._wait_tick)

    # ------------------------------------------------------------ 启动
    def start(self):
        ok = self.hooks.start()
        if not ok:
            return False
        self._build_tray()
        return True

    def shutdown(self):
        self._cursor_timer.stop()
        self._wait_timer.stop()
        self.hooks.stop()
        if self.tray:
            self.tray.hide()

    # ------------------------------------------------------------ 钩子回调（后台线程）
    def _on_key_raw(self, vk, is_down):
        """返回 True 表示吞掉该按键。此函数运行在钩子线程，必须快速返回。

        关键点：
        1) 低层钩子上报的修饰键是"左右具体码"（Alt = 0xA4），必须先归一化成 0x12，
           否则抬起事件对不上号会被当成普通键吞掉，系统就永远认为 Alt 按着。
        2) "已按下热键"的状态必须在本线程同步维护，不能依赖主线程的 wheel.active，
           否则快速按压时松开事件会在窗口打开前到达，导致转盘卡住不关闭。
        """
        if not self.enabled or self._record_paused:
            return False

        vk = keymod.normalize_vk(vk)
        now = time.monotonic()

        # 主线程迟迟没把转盘弹出来（异常情况）时自动解除武装，避免一直吞键
        # 1 秒内主线程还没把转盘弹出来，说明状态异常（例如被其它事件打断），
        # 自动解锁，避免后续按键被一直吞掉
        if self._armed and not self.wheel.active and (now - self._armed_ts) > 1.0:
            self._armed = False

        if self._armed or self.wheel.active:
            if is_down and vk == 0x1B:  # Esc 取消
                self._armed = False
                self._emit_cancel()
                return True
            if not is_down and (vk == self._armed_vk or vk in self._armed_mods):
                self._armed = False
                self.hotkey_released.emit()
                # 修饰键的抬起仍要透传，否则前台程序会以为修饰键一直按着
                return not keymod.is_modifier_vk(vk)
            # 修饰键透传：呼出时 Alt/Ctrl 的按下已经传给了前台程序，
            # 若把抬起也吞掉，前台程序会一直以为修饰键还按着。
            if keymod.is_modifier_vk(vk):
                return False
            # 其余按键全部吞掉，避免转盘打开时误触前台程序
            return True

        if not is_down:
            return False

        ctrl, alt, shift, win = native.modifier_state()
        for i, w in enumerate(self.cfg["wheels"]):
            hk = w.get("hotkey") or {}
            if keymod.normalize_vk(hk.get("vk", 0)) != vk:
                continue
            mods = hk.get("mods") or []
            if (
                ("ctrl" in mods) == ctrl
                and ("alt" in mods) == alt
                and ("shift" in mods) == shift
                and ("win" in mods) == win
            ):
                self._armed = True
                self._armed_vk = vk
                self._armed_mods = frozenset(
                    _MOD_STR_TO_VK[m] for m in mods if m in _MOD_STR_TO_VK
                )
                self._armed_ts = now
                self.hotkey_pressed.emit(i)
                return True
        return False

    def _on_wheel_raw(self, delta):
        if not self.enabled or not self.wheel.active:
            return False
        wheel_cfg = self.wheel.wheel_config()
        if not wheel_cfg or wheel_cfg.get("select_mode") != cfgmod.SELECT_WHEEL:
            return False
        self.wheel_scrolled.emit(1 if delta > 0 else -1)
        return True

    def _emit_cancel(self):
        # 由钩子线程调用，走信号回主线程
        self._cancel_pending = True
        self.hotkey_released.emit()  # 复用释放信号，主线程再判断取消标记
        # 注：为避免额外的信号定义，取消通过 _cancel_pending 标记传递

    # ------------------------------------------------------------ 主线程：打开/关闭
    def _open_wheel(self, index):
        if not (0 <= index < len(self.cfg["wheels"])):
            return
        wheel_cfg = self.cfg["wheels"][index]
        self._active_wheel = index
        self._cancel_pending = False
        self._pending_action = None
        hk_label = (wheel_cfg.get("hotkey") or {}).get("label", "")
        if wheel_cfg.get("show_hint", True):
            hint = "松开 %s 执行 · Esc 取消" % hk_label if hk_label else "Esc 取消"
        else:
            hint = ""
        self.wheel.open_wheel(wheel_cfg, hint=hint)
        self._cursor_timer.start()

    def _on_release(self):
        cancelled = self._cancel_pending
        # 点击过分区：转盘转为「悬停」状态，松开热键不关闭、不执行
        if self.wheel.click_locked and not cancelled:
            return
        self._cursor_timer.stop()
        idx = self.wheel.index
        wheel_cfg = self.wheel.wheel_config()
        self.wheel.close_wheel()

        if cancelled or idx < 0 or wheel_cfg is None:
            return
        segments = wheel_cfg.get("segments") or []
        if not (0 <= idx < len(segments)):
            return
        self._pending_action = segments[idx].get("action") or {}
        self._pending_wheel_cfg = wheel_cfg
        self._wait_ms = 0
        self._wait_limit = 1200
        self._wait_timer.start()

    # ------------------------------------------------------------ 鼠标点击
    def _on_segment_clicked(self, idx):
        """点击分区：立即执行，并把转盘锁定为悬停状态，可连续点按。"""
        wheel_cfg = self.wheel.wheel_config()
        if wheel_cfg is None:
            return
        segments = wheel_cfg.get("segments") or []
        if not (0 <= idx < len(segments)):
            return
        self.wheel.lock_open()
        self.wheel.update()

        action = segments[idx].get("action") or {}
        # 只有"发送按键"会被按住的修饰键污染，需要等松手；
        # 打开程序/网页/媒体键不受影响，立即执行才跟手。
        if action.get("type") != cfgmod.ACTION_KEYS:
            self._pending_action = None
            self._wait_timer.stop()
            ok, err = actions.execute(action)
            if not ok and self.tray:
                self.tray.showMessage("快捷转盘", err, QSystemTrayIcon.Warning, 2600)
            return

        self._pending_action = action
        self._pending_wheel_cfg = wheel_cfg
        self._wait_ms = 0
        self._wait_limit = 600
        self._wait_timer.start()

    def _on_dismiss(self):
        """点击中心圆 / 转盘外：取消并关闭。"""
        self._cancel_pending = True
        # 关键：点击关闭时热键可能仍按着，必须清掉"已武装"状态，
        # 否则松开前再按热键会被当成"转盘还开着"而吞掉，表现为呼不出来。
        self._armed = False
        self._cursor_timer.stop()
        self.wheel.close_wheel()
        self._pending_action = None
        self._wait_timer.stop()

    def _wait_tick(self):
        """等用户松开修饰键后再发按键，否则组合键会被污染。"""
        self._wait_ms += 20
        ctrl, alt, shift, win = native.modifier_state()
        if (ctrl or alt or shift or win) and self._wait_ms < self._wait_limit:
            return
        self._wait_timer.stop()
        action = self._pending_action
        self._pending_action = None
        if action:
            ok, err = actions.execute(action)
            if not ok and self.tray:
                self.tray.showMessage("快捷转盘", err, QSystemTrayIcon.Warning, 2600)

    def _poll_cursor(self):
        if not self.wheel.active:
            self._cursor_timer.stop()
            return
        x, y = native.get_cursor_pos()
        self.wheel.update_from_cursor(x, y)

    def _on_scroll(self, direction):
        self.wheel.cycle(direction)

    # ------------------------------------------------------------ 配置
    def apply_config(self, new_cfg, save=True):
        self.cfg = cfgmod.normalize_config(new_cfg)
        if save:
            try:
                cfgmod.save_config(self.cfg)
            except OSError as exc:
                if self.tray:
                    self.tray.showMessage("快捷转盘", "配置保存失败：%s" % exc, QSystemTrayIcon.Warning, 3000)
        return self.cfg

    # ------------------------------------------------------------ 托盘
    def _build_tray(self):
        self.tray = QSystemTrayIcon(make_app_icon(), self.app)
        self.tray.setToolTip("快捷转盘")

        menu = QMenu()
        act_settings = QAction("设置…", menu)
        act_settings.triggered.connect(self.show_settings)
        menu.addAction(act_settings)

        self._act_toggle = QAction("暂停热键", menu)
        self._act_toggle.triggered.connect(self._toggle_enabled)
        menu.addAction(self._act_toggle)

        menu.addSeparator()
        act_quit = QAction("退出", menu)
        act_quit.triggered.connect(self.quit)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_settings()

    def _toggle_enabled(self):
        self.enabled = not self.enabled
        self._act_toggle.setText("暂停热键" if self.enabled else "启用热键")
        self.tray.setToolTip("快捷转盘" + ("" if self.enabled else "（已暂停）"))

    def show_settings(self):
        from .settings_ui import SettingsWindow

        if self.settings is None:
            self.settings = SettingsWindow(
                self.cfg,
                on_saved=self._on_settings_saved,
                icon=make_app_icon(),
                on_recording=self._on_recording_state,
            )
        else:
            self.settings.reload(self.cfg)
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def _on_recording_state(self, recording):
        """设置界面录制按键时挂起热键，录制结束恢复。"""
        self._record_paused = bool(recording)

    def _on_settings_saved(self, new_cfg):
        self.apply_config(new_cfg)
        self._sync_startup(self.cfg.get("launch_at_startup", False))

    def _sync_startup(self, enable):
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    winreg.SetValueEx(key, cfgmod.APP_NAME, 0, winreg.REG_SZ, actions.startup_command())
                else:
                    try:
                        winreg.DeleteValue(key, cfgmod.APP_NAME)
                    except FileNotFoundError:
                        pass
        except OSError as exc:
            if self.tray:
                self.tray.showMessage("快捷转盘", "自启设置失败：%s" % exc, QSystemTrayIcon.Warning, 3000)

    def quit(self):
        self.shutdown()
        self.app.quit()
