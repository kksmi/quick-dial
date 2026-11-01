# -*- coding: utf-8 -*-
"""设置窗口：多轮盘标签页、参数配置、扇区编辑、配色与冲突检测。"""

import copy

from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
)

from . import config as cfgmod
from . import keys as keymod
from . import native
from . import theme
from .radial import WheelPreview


class RecordButton(QPushButton):
    """快捷键录制按钮：点击后按下任意组合键即记录。

    也允许单键（如 F9），右键清除。
    """

    captured = Signal(str)
    recordingChanged = Signal(bool)

    def __init__(self, placeholder="点击设置快捷键", style_name="Recorder", parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self.setObjectName(style_name)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._recording = False
        self._label = ""
        self.setToolTip("点击后按下组合键即可录制；右键清除")
        self.set_label("")

    def set_label(self, text):
        self._label = text or ""
        self.setText(self._label or self._placeholder)

    def label(self):
        return self._label

    def _set_recording(self, on):
        if on == self._recording:
            return
        self._recording = on
        self.recordingChanged.emit(on)
        self.setProperty("recording", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        if on:
            self.setText("请按下按键…")
            self.setFocus(Qt.OtherFocusReason)
            self.grabKeyboard()
        else:
            self.releaseKeyboard()
            self.set_label(self._label)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            # 右键清除
            self._label = ""
            self.set_label("")
            self.captured.emit("")
            return
        super().mousePressEvent(event)
        self._set_recording(True)

    def keyPressEvent(self, event):
        if not self._recording:
            super().keyPressEvent(event)
            return
        key = event.key()
        mods = event.modifiers()
        pure_mods = (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta)
        if key in pure_mods:
            event.accept()
            return
        if key == Qt.Key_Escape:
            self._set_recording(False)
            event.accept()
            return
        label = keymod.label_from_qt(key, mods)
        if label:
            self._label = label
            self.set_label(label)
            self.captured.emit(label)
        self._set_recording(False)
        event.accept()

    def focusOutEvent(self, event):
        if self._recording:
            self._set_recording(False)
        super().focusOutEvent(event)


class ColorButton(QPushButton):
    """色块按钮，点击打开取色器。"""

    changed = Signal(str)

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self._color = color if theme.is_valid_color(color) else "#3B82F6"
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 28)
        self._apply()

    def _apply(self):
        self.setStyleSheet(
            "QPushButton { background: %s; border: 1px solid rgba(0,0,0,0.12);"
            " border-radius: 8px; }" % self._color
        )
        self.setToolTip(self._color)

    def color(self):
        return self._color

    def set_color(self, color):
        if theme.is_valid_color(color) and color.upper() != self._color.upper():
            self._color = color.upper()
            self._apply()
            self.changed.emit(self._color)

    def mousePressEvent(self, event):
        color = QColorDialog.getColor(QColor(self._color), self, "选择颜色")
        if color.isValid():
            self.set_color(color.name().upper())


class SegmentTable(QTableWidget):
    """扇区编辑表格：颜色 / 名称 / 动作类型 / 动作内容。"""

    changed = Signal()
    recordingChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["颜色", "名称", "触发动作", "内容 / 快捷键"])
        self.verticalHeader().setVisible(False)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.verticalHeader().setDefaultSectionSize(44)
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.setColumnWidth(0, 56)
        self.setColumnWidth(1, 116)
        self.setColumnWidth(2, 132)
        self._wheel = None
        self._loading = False

    # ---------------------------------------------------- 构建
    def load(self, wheel):
        self._loading = True
        self._wheel = wheel
        segs = wheel.get("segments") or []
        self.setRowCount(len(segs))
        for i, seg in enumerate(segs):
            self._build_row(i, seg)
        self._loading = False

    def _build_row(self, row, seg):
        color_btn = ColorButton(seg.get("color"))
        color_btn.changed.connect(lambda c, r=row: self._on_color(r, c))
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(8, 0, 4, 0)
        lay.addWidget(color_btn)
        lay.addStretch(1)
        self.setCellWidget(row, 0, wrap)

        name_edit = QLineEdit(seg.get("name") or "")
        name_edit.setPlaceholderText("分区名称")
        name_edit.setStyleSheet(
            "QLineEdit { border: none; background: transparent; padding: 2px 4px; }"
            "QLineEdit:focus { border-bottom: 1px solid %s; }" % theme.UI_ACCENT
        )
        name_edit.textChanged.connect(lambda t, r=row: self._on_name(r, t))
        self.setCellWidget(row, 1, name_edit)

        type_combo = QComboBox()
        for key, label in cfgmod.ACTION_LABELS:
            type_combo.addItem(label, key)
        action = seg.get("action") or {}
        idx = type_combo.findData(action.get("type"))
        type_combo.setCurrentIndex(max(0, idx))
        type_combo.currentIndexChanged.connect(
            lambda _i, r=row, combo=type_combo: self._on_type(r, combo.currentData())
        )
        self.setCellWidget(row, 2, type_combo)

        self._set_value_widget(row, action.get("type"), action.get("value") or "")

    def _set_value_widget(self, row, atype, value):
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(0)
        if atype == cfgmod.ACTION_MEDIA:
            combo = QComboBox()
            for key, label in cfgmod.MEDIA_ACTIONS:
                combo.addItem(label, key)
            idx = combo.findData(value)
            combo.setCurrentIndex(max(0, idx))
            combo.currentIndexChanged.connect(
                lambda _i, r=row, c=combo: self._on_value(r, c.currentData())
            )
            lay.addWidget(combo)
        elif atype == cfgmod.ACTION_KEYS:
            # 直接录制真实按键，而不是手打字符串
            btn = RecordButton("点击录制按键", "RecorderSmall")
            btn.set_label(value)
            btn.captured.connect(lambda label, r=row: self._on_value(r, label))
            btn.recordingChanged.connect(self.recordingChanged)
            btn.setMinimumWidth(150)
            btn.setMaximumWidth(200)
            lay.addWidget(btn)
            lay.addStretch(1)
        else:
            edit = QLineEdit(value)
            if atype == cfgmod.ACTION_LAUNCH:
                edit.setPlaceholderText("如 C:\\Program Files\\App\\app.exe 或 notepad.exe")
            else:
                edit.setPlaceholderText("如 https://www.bing.com")
            edit.setStyleSheet(
                "QLineEdit { border: none; background: transparent; padding: 2px 4px; }"
                "QLineEdit:focus { border-bottom: 1px solid %s; }" % theme.UI_ACCENT
            )
            edit.textChanged.connect(lambda t, r=row: self._on_value(r, t))
            lay.addWidget(edit)
        self.setCellWidget(row, 3, holder)

    # ---------------------------------------------------- 回写
    def _seg(self, row):
        if not self._wheel:
            return None
        segs = self._wheel.get("segments") or []
        if 0 <= row < len(segs):
            return segs[row]
        return None

    def _on_color(self, row, color):
        seg = self._seg(row)
        if seg is None:
            return
        seg["color"] = color
        self._notify()

    def _on_name(self, row, text):
        seg = self._seg(row)
        if seg is None:
            return
        seg["name"] = text
        self._notify()

    def _on_type(self, row, atype):
        seg = self._seg(row)
        if seg is None or not atype:
            return
        default_value = ""
        if atype == cfgmod.ACTION_MEDIA:
            default_value = cfgmod.MEDIA_ACTIONS[0][0]
        seg["action"] = {"type": atype, "value": default_value}
        self._set_value_widget(row, atype, default_value)
        self._notify()

    def _on_value(self, row, value):
        seg = self._seg(row)
        if seg is None:
            return
        seg.setdefault("action", {})
        seg["action"]["value"] = value
        self._notify()

    def _notify(self):
        if not self._loading:
            self.changed.emit()


class SettingsWindow(QWidget):
    """无边框设置窗口。"""

    def __init__(self, cfg, on_saved=None, icon=None, on_recording=None):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("快捷转盘 · 设置")
        if icon:
            self.setWindowIcon(icon)

        # 自适应屏幕：小屏（1366×768 等）上自动缩小，避免窗口超出可视区
        screen_geo = QApplication.primaryScreen().availableGeometry()
        want_w, want_h = 1240, 900
        width = min(want_w, int(screen_geo.width() * 0.94))
        height = min(want_h, int(screen_geo.height() * 0.92))
        self.resize(width, height)
        self.setMinimumSize(min(1000, width), min(680, height))

        self._on_saved = on_saved
        self._on_recording = on_recording
        self._cfg = copy.deepcopy(cfgmod.normalize_config(cfg))
        self._cur = 0
        self._loading = False
        self._drag_pos = None

        self._build_ui()
        self._load_tabs()
        self._bind_current()

    # ---------------------------------------------------- 布局
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        root = QFrame()
        root.setObjectName("RootFrame")
        root.setStyleSheet(
            "#RootFrame { background: %s; border-radius: 16px; border: 1px solid %s; }"
            % (theme.UI_BG, theme.UI_BORDER)
        )
        outer.addWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ---- 标题栏
        title = QFrame()
        title.setObjectName("TitleBar")
        title.setFixedHeight(54)
        title.installEventFilter(self)
        tlay = QHBoxLayout(title)
        tlay.setContentsMargins(20, 0, 12, 0)
        tlay.setSpacing(10)
        logo = QLabel("◉")
        logo.setStyleSheet("color: %s; font-size: 18px; font-weight: 700;" % theme.UI_ACCENT)
        tname = QLabel("快捷转盘")
        tname.setObjectName("TitleText")
        tlay.addWidget(logo)
        tlay.addWidget(tname)
        tlay.addStretch(1)
        btn_min = QPushButton("—")
        btn_min.setObjectName("WinBtn")
        btn_min.setFixedSize(38, 30)
        btn_min.clicked.connect(self.showMinimized)
        btn_close = QPushButton("✕")
        btn_close.setObjectName("CloseBtn")
        btn_close.setFixedSize(38, 30)
        btn_close.clicked.connect(self.hide)
        tlay.addWidget(btn_min)
        tlay.addWidget(btn_close)
        lay.addWidget(title)
        self._title_bar = title

        # ---- 标签栏
        tab_wrap = QWidget()
        tab_wrap.setObjectName("TabWrap")
        tab_wrap.setStyleSheet("#TabWrap { background: transparent; }")
        tlay2 = QHBoxLayout(tab_wrap)
        tlay2.setContentsMargins(16, 10, 16, 0)
        tlay2.setSpacing(8)
        from PySide6.QtWidgets import QTabBar

        self.tabbar = QTabBar()
        self.tabbar.setDrawBase(False)
        self.tabbar.setExpanding(False)
        self.tabbar.currentChanged.connect(self._on_tab_changed)
        tlay2.addWidget(self.tabbar)
        tlay2.addStretch(1)
        self.btn_add = QToolButton()
        self.btn_add.setText("＋ 新建轮盘")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setStyleSheet(
            "QToolButton { border: 1px dashed #C9D4E8; border-radius: 9px; padding: 6px 12px;"
            " color: %s; background: #FFFFFF; }"
            "QToolButton:hover { border-color: %s; color: %s; }"
            % (theme.UI_SUB, theme.UI_ACCENT, theme.UI_ACCENT)
        )
        self.btn_add.clicked.connect(self._add_wheel)
        self.btn_del = QToolButton()
        self.btn_del.setText("删除")
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.setStyleSheet(
            "QToolButton { border: none; border-radius: 9px; padding: 6px 10px; color: %s; }"
            "QToolButton:hover { background: #FDE8E8; color: #DC2626; }" % theme.UI_SUB
        )
        self.btn_del.clicked.connect(self._remove_wheel)
        tlay2.addWidget(self.btn_add)
        tlay2.addWidget(self.btn_del)
        lay.addWidget(tab_wrap)

        # ---- 内容区
        body = QWidget()
        blay = QHBoxLayout(body)
        blay.setContentsMargins(16, 14, 16, 8)
        blay.setSpacing(14)

        # 左列：预览
        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(400)
        llay = QVBoxLayout(left)
        llay.setContentsMargins(14, 14, 14, 14)
        llay.setSpacing(10)
        cap = QLabel("实时预览")
        cap.setObjectName("CardTitle")
        llay.addWidget(cap)
        self.preview = WheelPreview()
        self.preview.setMinimumHeight(300)
        llay.addWidget(self.preview, 1)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(8)
        tlbl = QLabel("配色方案")
        tlbl.setObjectName("Hint")
        self.theme_combo = QComboBox()
        for key in theme.THEME_ORDER:
            self.theme_combo.addItem(theme.PALETTES[key]["name"], key)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(tlbl)
        theme_row.addWidget(self.theme_combo, 1)
        llay.addLayout(theme_row)

        accent_row = QHBoxLayout()
        accent_row.setSpacing(8)
        albl = QLabel("转盘主色")
        albl.setObjectName("Hint")
        self.accent_btn = ColorButton("#3B82F6")
        self.accent_btn.changed.connect(self._on_accent_changed)
        accent_row.addWidget(albl)
        accent_row.addWidget(self.accent_btn)
        accent_row.addStretch(1)
        llay.addLayout(accent_row)

        tip = QLabel("切换配色方案会按色板重设各分区颜色；单个分区颜色可在右侧表格单独调整。")
        tip.setObjectName("Hint")
        tip.setWordWrap(True)
        llay.addWidget(tip)
        blay.addWidget(left)

        # 右列
        right = QVBoxLayout()
        right.setSpacing(12)

        form_card = QFrame()
        form_card.setObjectName("Card")
        flay = QGridLayout(form_card)
        flay.setContentsMargins(16, 12, 16, 12)
        flay.setHorizontalSpacing(14)
        flay.setVerticalSpacing(8)

        def label(text):
            lb = QLabel(text)
            lb.setObjectName("SectionLabel")
            return lb

        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name_changed)

        self.hotkey_btn = RecordButton()
        self.hotkey_btn.captured.connect(self._on_hotkey_changed)
        self.hotkey_btn.recordingChanged.connect(self._notify_recording)

        self.position_combo = QComboBox()
        self.position_combo.addItem("跟随鼠标光标", cfgmod.POSITION_CURSOR)
        self.position_combo.addItem("屏幕居中", cfgmod.POSITION_CENTER)
        self.position_combo.currentIndexChanged.connect(self._on_position_changed)

        self.select_combo = QComboBox()
        self.select_combo.addItem("鼠标移动方向选中", cfgmod.SELECT_MOUSE)
        self.select_combo.addItem("滚轮切换选中", cfgmod.SELECT_WHEEL)
        self.select_combo.currentIndexChanged.connect(self._on_select_changed)

        self.count_spin = QSpinBox()
        self.count_spin.setRange(cfgmod.MIN_SEGMENTS, cfgmod.MAX_SEGMENTS)
        self.count_spin.valueChanged.connect(self._on_count_changed)

        size_box = QWidget()
        slay = QHBoxLayout(size_box)
        slay.setContentsMargins(0, 0, 0, 0)
        slay.setSpacing(10)
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(cfgmod.DIAMETER_MIN, cfgmod.DIAMETER_MAX)
        self.size_slider.setSingleStep(10)
        self.size_slider.setPageStep(40)
        self.size_slider.valueChanged.connect(self._on_size_changed)
        self.size_label = QLabel("360 px")
        self.size_label.setFixedWidth(64)
        self.size_label.setObjectName("Hint")
        slay.addWidget(self.size_slider, 1)
        slay.addWidget(self.size_label)

        sens_box = QWidget()
        slay2 = QHBoxLayout(sens_box)
        slay2.setContentsMargins(0, 0, 0, 0)
        slay2.setSpacing(10)
        self.sens_slider = QSlider(Qt.Horizontal)
        self.sens_slider.setRange(1, 10)
        self.sens_slider.valueChanged.connect(self._on_sens_changed)
        self.sens_label = QLabel("6 / 10")
        self.sens_label.setFixedWidth(64)
        self.sens_label.setObjectName("Hint")
        slay2.addWidget(self.sens_slider, 1)
        slay2.addWidget(self.sens_label)

        self.hint_check = QCheckBox("显示底部操作提示")
        self.hint_check.toggled.connect(self._on_hint_toggled)
        self.startup_check = QCheckBox("开机自动启动")
        self.startup_check.toggled.connect(self._on_startup_toggled)

        flay.addWidget(label("轮盘名称"), 0, 0)
        flay.addWidget(self.name_edit, 0, 1)
        flay.addWidget(label("呼出快捷键"), 0, 2)
        flay.addWidget(self.hotkey_btn, 0, 3)

        self.hotkey_status = QLabel("")
        self.hotkey_status.setObjectName("Hint")
        self.hotkey_status.setWordWrap(True)
        flay.addWidget(self.hotkey_status, 1, 2, 1, 2)

        flay.addWidget(label("呼出位置"), 2, 0)
        flay.addWidget(self.position_combo, 2, 1)
        flay.addWidget(label("分区数量"), 2, 2)
        flay.addWidget(self.count_spin, 2, 3)

        flay.addWidget(label("选中方式"), 3, 0)
        flay.addWidget(self.select_combo, 3, 1)
        flay.addWidget(label("灵敏度"), 3, 2)
        flay.addWidget(sens_box, 3, 3)

        flay.addWidget(label("转盘大小"), 4, 0)
        flay.addWidget(size_box, 4, 1, 1, 3)

        check_row = QHBoxLayout()
        check_row.setSpacing(18)
        check_row.addWidget(self.hint_check)
        check_row.addWidget(self.startup_check)
        check_row.addStretch(1)
        flay.addLayout(check_row, 5, 0, 1, 4)

        flay.setColumnStretch(1, 3)
        flay.setColumnStretch(3, 4)
        right.addWidget(form_card)

        table_card = QFrame()
        table_card.setObjectName("Card")
        tblay = QVBoxLayout(table_card)
        tblay.setContentsMargins(14, 12, 14, 12)
        tblay.setSpacing(8)
        head = QHBoxLayout()
        ttl = QLabel("分区设置")
        ttl.setObjectName("CardTitle")
        head.addWidget(ttl)
        head.addStretch(1)
        self.seg_hint = QLabel("按住热键呼出后，松开即执行所选动作")
        self.seg_hint.setObjectName("Hint")
        head.addWidget(self.seg_hint)
        tblay.addLayout(head)

        self.table = SegmentTable()
        self.table.changed.connect(self._update_preview)
        self.table.recordingChanged.connect(self._notify_recording)
        tblay.addWidget(self.table, 1)
        right.addWidget(table_card, 1)

        blay.addLayout(right, 1)
        lay.addWidget(body, 1)

        # ---- 底部按钮
        footer = QFrame()
        footer.setObjectName("Footer")
        footer.setMinimumHeight(66)
        footer.setStyleSheet("#Footer { background: transparent; }")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 4, 16, 16)
        fl.setSpacing(10)
        self.btn_import = QPushButton("导入配置")
        self.btn_import.clicked.connect(self._import)
        self.btn_export = QPushButton("导出配置")
        self.btn_export.clicked.connect(self._export)
        self.btn_reset = QPushButton("恢复默认")
        self.btn_reset.clicked.connect(self._reset)
        fl.addWidget(self.btn_import)
        fl.addWidget(self.btn_export)
        fl.addWidget(self.btn_reset)
        fl.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Hint")
        fl.addWidget(self.status)
        self.btn_save = QPushButton("保存并应用")
        self.btn_save.setObjectName("Primary")
        self.btn_save.setMinimumWidth(132)
        self.btn_save.setFixedHeight(40)
        self.btn_save.clicked.connect(self._save)
        fl.addWidget(self.btn_save)
        lay.addWidget(footer)

    def keyPressEvent(self, event):
        # 录制控件会自己抢键盘，这里只处理普通状态下的 Esc
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    # ---------------------------------------------------- 窗口拖动
    def eventFilter(self, obj, event):
        title_bar = getattr(self, "_title_bar", None)
        if title_bar is not None and obj is title_bar:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            if event.type() == QEvent.MouseMove and self._drag_pos is not None:
                self.move(event.globalPosition().toPoint() - self._drag_pos)
                return True
            if event.type() == QEvent.MouseButtonRelease:
                self._drag_pos = None
                return True
        return super().eventFilter(obj, event)

    # ---------------------------------------------------- 数据
    def _wheel(self):
        if 0 <= self._cur < len(self._cfg["wheels"]):
            return self._cfg["wheels"][self._cur]
        return None

    def reload(self, cfg):
        self._cfg = copy.deepcopy(cfgmod.normalize_config(cfg))
        self._load_tabs()
        self._bind_current()

    def _load_tabs(self):
        self._loading = True
        self.tabbar.blockSignals(True)
        while self.tabbar.count():
            self.tabbar.removeTab(0)
        for w in self._cfg["wheels"]:
            self.tabbar.addTab(w.get("name") or "轮盘")
        self.tabbar.blockSignals(False)
        if self.tabbar.count() == 0:
            self._cfg["wheels"].append(cfgmod.normalize_wheel({}))
            self.tabbar.addTab(self._cfg["wheels"][0]["name"])
        self._cur = max(0, min(self._cur, self.tabbar.count() - 1))
        self.tabbar.setCurrentIndex(self._cur)
        self._loading = False

    def _bind_current(self):
        """把当前轮盘的数据灌进各控件（期间屏蔽信号，避免连锁回写）。"""
        wheel = self._wheel()
        if wheel is None:
            return
        self._loading = True
        try:
            self.name_edit.setText(wheel.get("name") or "")
            self.hotkey_btn.set_label((wheel.get("hotkey") or {}).get("label", ""))
            self.position_combo.setCurrentIndex(
                max(0, self.position_combo.findData(wheel.get("position_mode")))
            )
            self.select_combo.setCurrentIndex(
                max(0, self.select_combo.findData(wheel.get("select_mode")))
            )
            self.count_spin.setValue(len(wheel.get("segments") or []))
            self.size_slider.setValue(int(wheel.get("diameter", cfgmod.DIAMETER_DEFAULT)))
            self.size_label.setText("%d px" % self.size_slider.value())
            self.sens_slider.setValue(int(wheel.get("sensitivity", 6)))
            self.sens_label.setText("%d / 10" % self.sens_slider.value())
            self.sens_slider.setEnabled(wheel.get("select_mode") == cfgmod.SELECT_MOUSE)
            self.hint_check.setChecked(bool(wheel.get("show_hint", True)))
            self.startup_check.setChecked(bool(self._cfg.get("launch_at_startup", False)))
            self.accent_btn.set_color(wheel.get("accent") or "#3B82F6")
            idx = self.theme_combo.findData(wheel.get("theme"))
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
            self.table.load(wheel)
            self._update_preview()
            self._check_hotkey()
        finally:
            self._loading = False

    # ---------------------------------------------------- 控件回调
    def _on_tab_changed(self, index):
        if self._loading:
            return
        self._cur = index
        self._bind_current()

    def _add_wheel(self):
        used = {w["hotkey"]["label"] for w in self._cfg["wheels"]}
        candidates = ["Alt+E", "Alt+R", "Alt+T", "Alt+A", "Alt+S", "Alt+D", "Alt+G", "Alt+Z"]
        hotkey = next((c for c in candidates if c not in used), "Alt+Z")
        wheel = cfgmod.make_wheel(name="轮盘 %d" % (len(self._cfg["wheels"]) + 1), hotkey_label=hotkey)
        self._cfg["wheels"].append(wheel)
        self._load_tabs()
        self._cur = len(self._cfg["wheels"]) - 1
        self.tabbar.setCurrentIndex(self._cur)
        self._bind_current()

    def _remove_wheel(self):
        if len(self._cfg["wheels"]) <= 1:
            QMessageBox.information(self, "提示", "至少保留一个轮盘。")
            return
        name = self._wheel().get("name") or "轮盘"
        ret = QMessageBox.question(self, "删除轮盘", "确定删除「%s」？" % name)
        if ret != QMessageBox.Yes:
            return
        self._cfg["wheels"].pop(self._cur)
        self._cur = max(0, self._cur - 1)
        self._load_tabs()
        self._bind_current()

    def _on_name_changed(self, text):
        wheel = self._wheel()
        if wheel is None or self._loading:
            return
        wheel["name"] = text.strip() or "轮盘"
        self.tabbar.setTabText(self._cur, wheel["name"])
        self._update_preview()

    def _on_hotkey_changed(self, label):
        wheel = self._wheel()
        if wheel is None or self._loading:
            return
        mods, vk = keymod.parse_label(label)
        if vk is None:
            self._set_hotkey_status("无法识别该按键，请重试", "Danger")
            return
        wheel["hotkey"] = {"vk": vk, "mods": mods, "label": keymod.make_label(mods, vk)}
        self.hotkey_btn.set_label(wheel["hotkey"]["label"])
        self._check_hotkey()

    def _on_position_changed(self, _i):
        wheel = self._wheel()
        if wheel is None or self._loading:
            return
        wheel["position_mode"] = self.position_combo.currentData()
        self._update_preview()

    def _on_select_changed(self, _i):
        wheel = self._wheel()
        if wheel is None or self._loading:
            return
        wheel["select_mode"] = self.select_combo.currentData()
        self.sens_slider.setEnabled(wheel["select_mode"] == cfgmod.SELECT_MOUSE)
        self._update_preview()

    def _on_count_changed(self, value):
        wheel = self._wheel()
        if wheel is None or self._loading:
            return
        cfgmod.resize_segments(wheel, value)
        self.table.load(wheel)
        self._update_preview()

    def _on_size_changed(self, value):
        wheel = self._wheel()
        if wheel is None or self._loading:
            return
        wheel["diameter"] = int(value)
        self.size_label.setText("%d px" % value)
        self._update_preview()

    def _on_sens_changed(self, value):
        wheel = self._wheel()
        if wheel is None or self._loading:
            return
        wheel["sensitivity"] = int(value)
        self.sens_label.setText("%d / 10" % value)

    def _on_hint_toggled(self, checked):
        wheel = self._wheel()
        if wheel is None or self._loading:
            return
        wheel["show_hint"] = bool(checked)

    def _on_startup_toggled(self, checked):
        if self._loading:
            return
        self._cfg["launch_at_startup"] = bool(checked)

    def _on_accent_changed(self, color):
        wheel = self._wheel()
        if wheel is None or self._loading:
            return
        wheel["accent"] = color
        self._update_preview()

    def _on_theme_changed(self, _index):
        wheel = self._wheel()
        if wheel is None or self._loading:
            return
        key = self.theme_combo.currentData()
        palette = theme.get_palette(key)
        wheel["theme"] = key
        wheel["accent"] = palette[0]
        for i, seg in enumerate(wheel.get("segments") or []):
            seg["color"] = palette[i % len(palette)]
        self._loading = True
        self.accent_btn.set_color(palette[0])
        self._loading = False
        self.table.load(wheel)
        self._update_preview()

    # ---------------------------------------------------- 预览与冲突
    def _notify_recording(self, on):
        """录制按键期间让主程序暂停热键，否则录到的组合会被自己抢走。"""
        if self._on_recording:
            self._on_recording(bool(on))

    def _update_preview(self):
        wheel = self._wheel()
        if wheel is None:
            return
        self.preview.set_wheel(wheel, index=0 if wheel.get("segments") else -1)

    def _set_hotkey_status(self, text, kind="Hint"):
        self.hotkey_status.setObjectName(kind)
        self.hotkey_status.setText(text)
        self.hotkey_status.style().unpolish(self.hotkey_status)
        self.hotkey_status.style().polish(self.hotkey_status)

    def _check_hotkey(self):
        """冲突检测：系统保留组合 / 本程序其它轮盘 / 系统已注册占用。"""
        wheel = self._wheel()
        if wheel is None:
            return True
        hk = wheel.get("hotkey") or {}
        mods = hk.get("mods") or []
        vk = int(hk.get("vk", 0))
        label = hk.get("label") or ""

        for i, other in enumerate(self._cfg["wheels"]):
            if i == self._cur:
                continue
            ohk = other.get("hotkey") or {}
            if int(ohk.get("vk", 0)) == vk and set(ohk.get("mods") or []) == set(mods):
                self._set_hotkey_status("与「%s」冲突，请更换" % (other.get("name") or "其它轮盘"), "Danger")
                return False

        reserved = keymod.check_reserved(mods, vk)
        if reserved:
            self._set_hotkey_status("系统保留组合（%s），可能无法生效" % reserved, "Warn")
            return True

        if not mods and not (0x70 <= vk <= 0x87):
            self._set_hotkey_status("未加修饰键的单键会被拦截，正常打字将失效，建议加 Ctrl/Alt", "Warn")
            return True

        free, reason = native.probe_hotkey(vk, mods)
        if not free:
            self._set_hotkey_status("%s（%s），仍可尝试使用" % (reason, label), "Warn")
            return True

        self._set_hotkey_status("组合键可用", "Ok")
        return True

    # ---------------------------------------------------- 保存 / 导入导出
    def _save(self):
        if not self._check_hotkey():
            QMessageBox.warning(self, "快捷键冲突", "当前轮盘的呼出快捷键与其它轮盘重复，请先修改。")
            return
        # 保存前做一次完整规范化，清掉编辑过程中可能出现的空名称等
        normalized = cfgmod.normalize_config(self._cfg)
        self._cfg = copy.deepcopy(normalized)
        if self._on_saved:
            self._on_saved(normalized)
        self.status.setText("已保存 · %s" % cfgmod.config_path())
        self._load_tabs()
        self._bind_current()
        self.hide()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", "quickdial-config.json", "JSON 配置 (*.json)"
        )
        if not path:
            return
        try:
            cfgmod.export_config(self._cfg, path)
            self.status.setText("已导出：%s" % path)
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入配置", "", "JSON 配置 (*.json)")
        if not path:
            return
        try:
            cfg = cfgmod.import_config(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "导入失败", "文件无法解析：%s" % exc)
            return
        self._cfg = copy.deepcopy(cfg)
        self._cur = 0
        self._load_tabs()
        self._bind_current()
        self.status.setText("已导入，点击「保存并应用」生效")

    def _reset(self):
        ret = QMessageBox.question(self, "恢复默认", "将当前轮盘重置为默认配置，确定继续？")
        if ret != QMessageBox.Yes:
            return
        self._cfg["wheels"][self._cur] = cfgmod.normalize_wheel({})
        self._bind_current()
        self.status.setText("已重置，点击「保存并应用」生效")
