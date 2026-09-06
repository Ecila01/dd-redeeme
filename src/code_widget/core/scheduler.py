"""定时调度模块（F2/F8）：轮询 QTimer + 每日检查 QTimer，全部运行在 Qt 主线程。

- 轮询：每 fetch.interval_minutes 触发一次 service.refresh()
- 每日：单发 QTimer 定时到 fetch.daily_check_time，触发后重新装载次日定时器
  （挂机跨天也能继续）
- reconfigure()：设置页保存后按新配置重启定时器（F11 热生效）
- 网络请求绝不在此模块内直接发起（由 CodeService 抛给 QThreadPool）
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QTimer

from .models import today_str

log = logging.getLogger(__name__)


def ms_until_next(time_hhmm: str, now: datetime | None = None) -> int:
    """距下一个 time_hhmm（当日未到取当日，已过取次日）的毫秒数；边界整点取次日。"""
    hh, mm = (int(x) for x in time_hhmm.split(":"))
    now = now or datetime.now()
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max(1_000, int((target - now).total_seconds() * 1000))


class Scheduler(QObject):
    """依赖注入 service / cfg / cache；在 main.py 中装配并 start()。"""

    def __init__(self, service, cfg, cache, parent=None):
        super().__init__(parent)
        self._service, self._cfg, self._cache = service, cfg, cache
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._service.refresh)
        self._daily_timer = QTimer(self)
        self._daily_timer.setSingleShot(True)
        self._daily_timer.timeout.connect(self._on_daily)

    def start(self) -> None:
        self.reconfigure()

    def reconfigure(self) -> None:
        """设置变更后调用：按新配置重启两个定时器。"""
        minutes = max(1, int(self._cfg.get("fetch.interval_minutes", 30)))
        self._poll_timer.start(minutes * 60 * 1000)
        self._arm_daily()
        log.info("调度生效：轮询 %d 分钟，每日检查 %s",
                 minutes, self._cfg.get("fetch.daily_check_time", "12:00"))

    def _arm_daily(self) -> None:
        self._daily_timer.start(ms_until_next(self._cfg.get("fetch.daily_check_time", "12:00")))

    def _on_daily(self) -> None:
        if self._cache.state.last_daily_check != today_str():   # 当日去重（F8）
            log.info("每日检查触发")
            self._service.refresh()
            self._cache.set_last_daily_check(today_str())
        self._arm_daily()   # 重新装载次日定时器，挂机跨天不失效
