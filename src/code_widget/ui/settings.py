"""设置页（M4，简版）：配置编辑 → ConfigManager 落盘 → settingsApplied 信号。

- 覆盖：数据源列表（启停/URL/顺序）、轮询间隔、每日时间、启动检查、
  通知三开关、界面（缩放/透明度/置顶/吸附）、开机自启动。
- 热生效不在本页做：发 settingsApplied 信号，由 main.py 统一分发到各模块
  （service.reconfigure / scheduler.reconfigure / widget.apply_ui_settings /
  notifier.set_enabled / tray.sync_autostart）。
- 红线说明：配置编辑是本页职责，仅通过 ConfigManager 读写；不触业务数据 IO。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QTimeEdit, QVBoxLayout)

from .. import APP_NAME_CN, APP_NAME_EN
from ..core import autostart
from ..core.config import ConfigManager


class SettingsDialog(QDialog):
    settingsApplied = Signal()

    def __init__(self, cfg: ConfigManager, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self.setWindowTitle(f"{APP_NAME_CN} {APP_NAME_EN} · 设置")
        self.setMinimumSize(600, 620)
        self._build()
        self.load()

    # ---------- 构建 ----------
    def _build(self) -> None:
        lay = QVBoxLayout(self)

        # 数据源（有序回退）
        src_box = QGroupBox("数据源（自上而下依次尝试，失败自动回退）")
        sv = QVBoxLayout(src_box)
        self._sources = QTableWidget(0, 3)
        self._sources.setHorizontalHeaderLabels(["启用", "名称", "URL"])
        self._sources.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._sources.setColumnWidth(0, 36)
        self._sources.setColumnWidth(1, 110)
        self._sources.verticalHeader().setVisible(False)
        sv.addWidget(self._sources)

        sbtns = QHBoxLayout()
        for text, cb in (("添加", self._add_source), ("删除", self._del_source),
                         ("上移", lambda: self._move_source(-1)),
                         ("下移", lambda: self._move_source(1))):
            b = QPushButton(text)
            b.clicked.connect(cb)
            sbtns.addWidget(b)
        sbtns.addStretch(1)
        sv.addLayout(sbtns)
        lay.addWidget(src_box)

        # 拉取
        fetch_box = QGroupBox("拉取")
        ff = QFormLayout(fetch_box)
        self._interval = QSpinBox()
        self._interval.setRange(1, 1440)
        self._interval.setSuffix(" 分钟")
        self._daily = QTimeEdit()
        self._daily.setDisplayFormat("HH:mm")
        self._startup_check = QCheckBox("当日首次启动时立即检查更新")
        ff.addRow("轮询间隔", self._interval)
        ff.addRow("每日检查时间", self._daily)
        ff.addRow("", self._startup_check)
        lay.addWidget(fetch_box)

        # 通知
        notify_box = QGroupBox("通知")
        nv = QVBoxLayout(notify_box)
        self._notify_master = QCheckBox("启用系统通知")
        self._notify_new = QCheckBox("发现新兑换码时通知")
        self._notify_err = QCheckBox("拉取失败时提醒（每天最多一次，防打扰）")
        nv.addWidget(self._notify_master)
        nv.addWidget(self._notify_new)
        nv.addWidget(self._notify_err)
        lay.addWidget(notify_box)

        # 界面
        ui_box = QGroupBox("界面")
        uf = QFormLayout(ui_box)
        self._scale = QDoubleSpinBox()
        self._scale.setRange(0.6, 2.5)
        self._scale.setSingleStep(0.1)
        self._scale.setSuffix(" 倍")
        self._opacity = QDoubleSpinBox()
        self._opacity.setRange(0.5, 1.0)
        self._opacity.setSingleStep(0.05)
        self._on_top = QCheckBox("窗口置顶")
        self._snap = QCheckBox("贴边自动吸附")
        uf.addRow("挂件缩放", self._scale)
        uf.addRow("窗口透明度", self._opacity)
        uf.addRow("", self._on_top)
        uf.addRow("", self._snap)
        self._bubble_secs = QSpinBox()
        self._bubble_secs.setRange(0, 60)
        self._bubble_secs.setSuffix(" 秒")
        self._bubble_secs.setSpecialValueText("常驻（点击收起）")
        uf.addRow("气泡自动隐藏", self._bubble_secs)
        lay.addWidget(ui_box)

        # 系统
        sys_box = QGroupBox("系统")
        syv = QVBoxLayout(sys_box)
        self._autostart = QCheckBox("开机自动启动（当前用户，写入注册表 Run 键）")
        syv.addWidget(self._autostart)
        lay.addWidget(sys_box)

        # 按钮
        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("确定")
        ok.setDefault(True)
        cancel = QPushButton("取消")
        ok.clicked.connect(self._save)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        lay.addLayout(btns)

    # ---------- 读取/写入界面 ----------
    def load(self) -> None:
        """每次打开都从当前配置刷新（含托盘等其他入口的修改）。"""
        c = self._cfg
        rows = c.get("data_sources", []) or []
        self._sources.setRowCount(len(rows))
        for r, s in enumerate(rows):
            en = QTableWidgetItem()
            en.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsEnabled)
            en.setCheckState(Qt.Checked if s.get("enabled", True) else Qt.Unchecked)
            self._sources.setItem(r, 0, en)
            self._sources.setItem(r, 1, QTableWidgetItem(str(s.get("name", ""))))
            self._sources.setItem(r, 2, QTableWidgetItem(str(s.get("url", ""))))

        self._interval.setValue(int(c.get("fetch.interval_minutes", 30)))
        hh, mm = str(c.get("fetch.daily_check_time", "12:00")).split(":")
        self._daily.setTime(QTime(int(hh), int(mm)))
        self._startup_check.setChecked(bool(c.get("fetch.check_on_startup", True)))

        self._notify_master.setChecked(bool(c.get("notify.enabled", True)))
        self._notify_new.setChecked(bool(c.get("notify.on_new_codes", True)))
        self._notify_err.setChecked(bool(c.get("notify.on_fetch_error", False)))

        self._scale.setValue(float(c.get("ui.scale", 1.0)))
        self._opacity.setValue(float(c.get("ui.opacity", 0.95)))
        self._on_top.setChecked(bool(c.get("ui.always_on_top", True)))
        self._snap.setChecked(bool(c.get("ui.snap_enabled", True)))
        self._bubble_secs.setValue(int(c.get("ui.bubble_seconds", 5)))

        self._autostart.setChecked(autostart.is_enabled())   # 以注册表真实状态为准

    def _read_sources(self) -> list[dict]:
        rows = []
        for r in range(self._sources.rowCount()):
            en = self._sources.item(r, 0)
            name = self._sources.item(r, 1)
            url = self._sources.item(r, 2)
            rows.append({
                "enabled": bool(en and en.checkState() == Qt.Checked),
                "name": name.text().strip() if name else "",
                "type": "github_raw",
                "url": url.text().strip() if url else "",
            })
        return rows

    def _write_sources(self, rows: list[dict]) -> None:
        self._sources.setRowCount(len(rows))
        for r, s in enumerate(rows):
            en = QTableWidgetItem()
            en.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            en.setCheckState(Qt.Checked if s.get("enabled", True) else Qt.Unchecked)
            self._sources.setItem(r, 0, en)
            self._sources.setItem(r, 1, QTableWidgetItem(s.get("name", "")))
            self._sources.setItem(r, 2, QTableWidgetItem(s.get("url", "")))

    # ---------- 数据源行操作 ----------
    def _add_source(self) -> None:
        rows = self._read_sources()
        rows.append({"enabled": True, "name": "new-source", "type": "github_raw",
                     "url": "https://example.com/codes.json"})
        self._write_sources(rows)

    def _del_source(self) -> None:
        r = self._sources.currentRow()
        if r >= 0:
            self._sources.removeRow(r)

    def _move_source(self, delta: int) -> None:
        r = self._sources.currentRow()
        t = r + delta
        if r < 0 or t < 0 or t >= self._sources.rowCount():
            return
        rows = self._read_sources()
        rows[r], rows[t] = rows[t], rows[r]
        self._write_sources(rows)
        self._sources.selectRow(t)

    # ---------- 保存 ----------
    def _save(self) -> None:
        c = self._cfg
        c.set("data_sources", [x for x in self._read_sources() if x["url"]])
        c.set("fetch.interval_minutes", int(self._interval.value()))
        c.set("fetch.daily_check_time", self._daily.time().toString("HH:mm"))
        c.set("fetch.check_on_startup", self._startup_check.isChecked())
        c.set("notify.enabled", self._notify_master.isChecked())
        c.set("notify.on_new_codes", self._notify_new.isChecked())
        c.set("notify.on_fetch_error", self._notify_err.isChecked())
        c.set("ui.scale", round(self._scale.value(), 2))
        c.set("ui.opacity", round(self._opacity.value(), 2))
        c.set("ui.always_on_top", self._on_top.isChecked())
        c.set("ui.snap_enabled", self._snap.isChecked())
        c.set("ui.bubble_seconds", int(self._bubble_secs.value()))
        c.set("general.autostart", self._autostart.isChecked())
        c.save()

        try:
            if autostart.is_enabled() != self._autostart.isChecked():
                autostart.set_enabled(self._autostart.isChecked())
        except OSError:
            pass   # 托盘 sync_autostart 会把勾选回滚成注册表真实状态
        self.settingsApplied.emit()
        self.accept()
