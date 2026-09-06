"""系统托盘图标与右键菜单（M3）。

菜单：显示/隐藏挂件 · 立即刷新 · 测试通知 ┃ 打开数据仓库 ┃ 开机自启动√ · 设置… ┃ 退出
双击托盘 = 显示/隐藏挂件；关闭挂件窗口 = 隐藏到托盘（见 widget.closeEvent）。
红线：菜单动作只调用 service 公开方法 / 打开 URL / 发信号，不做业务 IO。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .. import APP_NAME_CN, APP_NAME_EN, __version__
from ..core import autostart

log = logging.getLogger(__name__)


def asset(name: str) -> Path:
    """定位资源：开发模式=仓库根 assets/；打包(onefile)=sys._MEIPASS/assets/。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    return base / "assets" / name


class TrayIcon(QSystemTrayIcon):
    settingsRequested = Signal()   # main.py 接线：打开设置页（M4）

    def __init__(self, widget, service, cfg, parent=None):
        super().__init__(QIcon(str(asset("fish.png"))), parent)
        self._widget, self._service, self._cfg = widget, service, cfg
        self.setToolTip(f"{APP_NAME_CN} {APP_NAME_EN} v{__version__}")

        menu = QMenu()
        menu.addAction("显示 / 隐藏挂件", widget.toggle)
        menu.addAction("立即刷新", service.refresh)
        menu.addAction("测试通知", self._test_notify)
        menu.addSeparator()
        repo_url = cfg.get("general.repo_url", "")
        if repo_url:
            menu.addAction("打开数据仓库", lambda: QDesktopServices.openUrl(QUrl(repo_url)))

        self._act_auto = QAction("开机自启动", menu, checkable=True)
        self._act_auto.setChecked(autostart.is_enabled())
        self._act_auto.toggled.connect(self._toggle_autostart)
        menu.addAction(self._act_auto)

        act_settings = QAction("设置…", menu)
        act_settings.triggered.connect(self.settingsRequested.emit)
        menu.addAction(act_settings)
        menu.addSeparator()
        menu.addAction("退出", self._quit)
        self.setContextMenu(menu)

        self.activated.connect(self._on_activated)

    # ---------- 行为 ----------
    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._widget.toggle()        # 双击托盘 = 显示/隐藏挂件

    def _test_notify(self) -> None:
        self.showMessage(f"{APP_NAME_CN} {APP_NAME_EN}",
                         "这是一条测试通知：托盘通知工作正常 ✓",
                         QSystemTrayIcon.Information, 6000)

    def _toggle_autostart(self, on: bool) -> None:
        try:
            autostart.set_enabled(on)
        except OSError as e:
            log.error("自启动设置失败: %s", e)
            self._act_auto.setChecked(not on)   # 回滚勾选
            return
        self._cfg.set("general.autostart", bool(on))
        self._cfg.save()

    def sync_autostart(self) -> None:
        """设置页修改自启动后，把菜单勾选同步为注册表真实状态。"""
        self._act_auto.setChecked(autostart.is_enabled())

    def _quit(self) -> None:
        self.hide()
        # TODO(M4): 停止 Scheduler、落盘缓存等资源清理
        from PySide6.QtWidgets import QApplication

        QApplication.quit()
