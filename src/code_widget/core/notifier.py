"""通知模块。当前实现：Qt 托盘气泡（Win10+ 显示为原生 Toast）。

前提：进程启动时已设置 AppUserModelID（见 main.py），且托盘图标已创建并 show。
替换实现（如 Windows 原生 API、微信/邮件推送）只需新增 BaseNotifier 子类。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class BaseNotifier(ABC):
    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    def set_enabled(self, on: bool) -> None:
        self._enabled = on

    @abstractmethod
    def notify(self, title: str, body: str) -> None: ...


class TrayNotifier(BaseNotifier):
    """基于 QSystemTrayIcon.showMessage。tray_icon=None 时仅记日志（无头/单测场景）。"""

    def __init__(self, tray_icon=None, enabled: bool = True):
        super().__init__(enabled)
        self._tray = tray_icon

    def set_tray(self, tray_icon) -> None:
        """托盘图标就绪后注入（main.py 在装配完成后调用）。"""
        self._tray = tray_icon

    def notify(self, title: str, body: str) -> None:
        if not self._enabled:
            return
        log.info("[通知] %s | %s", title, body)
        if self._tray is not None:
            from PySide6.QtWidgets import QSystemTrayIcon

            self._tray.showMessage(title, body, QSystemTrayIcon.Information, 6000)
        # TODO(M3): showMessage 返回 False / 专注助手拦截时，降级为挂件角标提示
