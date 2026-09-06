"""程序入口：AppUserModelID → 日志 → 装配各模块 → Qt 主循环。

运行：在 src 目录下执行  python -m code_widget.main
"""
from __future__ import annotations

import ctypes
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import APP_ID, APP_NAME_CN, APP_NAME_EN, __version__


def _setup_logging(log_dir: Path) -> None:
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_dir / "widget.log", maxBytes=1_000_000,
                                      backupCount=3, encoding="utf-8")
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                            handlers=[handler, logging.StreamHandler()])
    except OSError:  # 日志失败不阻塞启动
        logging.basicConfig(level=logging.INFO)


def main() -> int:
    # Windows 原生通知的归属标识，必须最先设置（否则 Toast 可能不弹/归属错误）
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    from PySide6.QtWidgets import QApplication

    from .core.cache import JsonFileCache
    from .core.config import ConfigManager
    from .core.notifier import TrayNotifier
    from .core.parser import CodesJsonParser
    from .core.scheduler import Scheduler
    from .service import CodeService
    from .ui.settings import SettingsDialog
    from .ui.tray import TrayIcon
    from .ui.widget import WidgetWindow

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME_EN)       # DD RedeeMe（内部名）
    app.setApplicationDisplayName(APP_NAME_CN)  # 兑了么（窗口/任务栏显示名）
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口 = 隐藏到托盘（F10）

    cfg = ConfigManager()
    _setup_logging(cfg.cache_dir / "logs")
    log = logging.getLogger(__name__)

    cache = JsonFileCache(cfg.cache_dir / "cache.json")
    notifier = TrayNotifier(enabled=bool(cfg.get("notify.enabled", True)))
    service = CodeService(cfg, cache, CodesJsonParser(), notifier)

    widget = WidgetWindow(cfg)
    tray = TrayIcon(widget, service, cfg)
    widget.set_context_menu(tray.contextMenu())   # F10：挂件右键复用托盘菜单

    # View ↔ Service 接线（M2）：UI 只经信号/槽与业务层通信
    service.codesUpdated.connect(widget.on_codes_updated)
    service.fetchStarted.connect(widget.on_fetch_started)
    service.fetchFinished.connect(widget.on_fetch_finished)
    service.newCodesFound.connect(widget.on_new_codes)
    widget.refreshRequested.connect(service.refresh)
    widget.markRequested.connect(service.mark_code)
    widget.on_codes_updated(service.current_items())   # 启动先用缓存离线渲染

    notifier.set_tray(tray)   # M3：通知走托盘 showMessage（Windows 原生 Toast）
    scheduler = Scheduler(service, cfg, cache)
    scheduler.start()

    # 设置页（M4）：单例 + 保存后统一热生效
    settings_holder: dict = {}

    def open_settings() -> None:
        dlg = settings_holder.get("dlg")
        if dlg is None:
            dlg = SettingsDialog(cfg)
            dlg.settingsApplied.connect(apply_settings)
            settings_holder["dlg"] = dlg
        dlg.load()
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def apply_settings() -> None:
        service.reconfigure()
        scheduler.reconfigure()
        notifier.set_enabled(bool(cfg.get("notify.enabled", True)))
        widget.apply_ui_settings(cfg)
        tray.sync_autostart()
        log.info("设置已保存并热生效")

    tray.settingsRequested.connect(open_settings)
    widget.show()
    tray.show()
    service.start()

    log.info("%s (%s) 启动完成 v%s", APP_NAME_CN, APP_NAME_EN, __version__)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
