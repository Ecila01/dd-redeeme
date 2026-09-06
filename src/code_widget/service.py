"""CodeService：业务编排中枢，UI 与基础设施的唯一桥梁（F13-4）。

View 层约定：
- 只能调用本类公开方法（refresh / mark_code / current_items / start / reconfigure）；
- 只能通过本类信号接收数据（codesUpdated / newCodesFound / fetchStarted / fetchFinished）；
- 本类不 import 任何 ui 模块。
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from .core.cache import BaseCache
from .core.fetcher import FetchError, NotModified, build_fetchers_from_config
from .core.models import now_iso, today_str
from .core.notifier import BaseNotifier
from .core.parser import BaseParser

log = logging.getLogger(__name__)

ERR_MSG = "数据暂时无法更新，已沿用本地缓存"  # F12 固定文案


class _FetchSignals(QObject):
    done = Signal(object)          # RawPayload
    fail = Signal(str)
    not_modified = Signal()


class _FetchJob(QRunnable):
    """在工作线程中执行网络请求，结果以信号送回主线程。"""

    def __init__(self, fetcher):
        super().__init__()
        self._fetcher = fetcher
        self.signals = _FetchSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.done.emit(self._fetcher.fetch())
        except NotModified:
            self.signals.not_modified.emit()
        except FetchError as e:
            self.signals.fail.emit(str(e))
        except Exception as e:  # 兜底：任何异常不允许留在工作线程
            log.exception("未预期的拉取异常")
            self.signals.fail.emit(str(e))


class CodeService(QObject):
    fetchStarted = Signal()
    fetchFinished = Signal(bool, str)   # ok, message
    codesUpdated = Signal(list)         # list[CodeItem]（已合并本地标记）
    newCodesFound = Signal(list)        # list[CodeItem]（本次新增，供 UI 高亮）

    def __init__(self, cfg, cache: BaseCache, parser: BaseParser, notifier: BaseNotifier):
        super().__init__()
        self._cfg, self._cache = cfg, cache
        self._parser, self._notifier = parser, notifier
        self._pool = QThreadPool.globalInstance()
        self._fetching = False
        self._error_notified_day = ""   # 错误提示防打扰：每天最多一次
        self._build_fetcher()

    def _build_fetcher(self) -> None:
        self._fetcher = build_fetchers_from_config(self._cfg, self._cache.state.etags)

    # ---------- 对 View 开放的接口 ----------
    def current_items(self) -> list:
        return self._cache.merge_marks(self._cache.state.items)

    def mark_code(self, uid: str, status: str | None) -> None:
        self._cache.set_mark(uid, status)
        self.codesUpdated.emit(self.current_items())

    def reconfigure(self) -> None:
        """设置页保存后调用：数据源可能已变更。"""
        self._build_fetcher()

    def start(self) -> None:
        """启动检查（F8 的"当日首次启动"场景）。"""
        if (self._cfg.get("fetch.check_on_startup", True)
                and self._cache.state.last_daily_check != today_str()):
            self.refresh()
            self._cache.set_last_daily_check(today_str())

    def refresh(self, manual: bool = False) -> None:
        """拉取最新数据（异步，结果经信号返回）。"""
        if self._fetching:
            return
        self._fetching = True
        self.fetchStarted.emit()
        job = _FetchJob(self._fetcher)
        job.signals.done.connect(self._on_fetch_done)
        job.signals.fail.connect(self._on_fetch_fail)
        job.signals.not_modified.connect(self._on_not_modified)
        self._pool.start(job)

    # ---------- 内部 ----------
    def _on_not_modified(self) -> None:
        self._finish(ok=True, msg="数据无更新")

    def _on_fetch_done(self, payload) -> None:
        try:
            fresh = self._parser.parse(payload)
        except Exception as e:  # ParseError 及一切解析异常：保留旧缓存
            log.error("解析失败: %s", e)
            self._finish(ok=False, msg="数据格式异常，已沿用本地缓存")
            return

        first_run = not self._cache.state.items
        result = self._cache.diff(fresh)
        self._cache.save_items(fresh, {"last_fetch_at": now_iso()})
        self.codesUpdated.emit(self._cache.merge_marks(fresh))

        if result.new_items and not first_run and self._cfg.get("notify.on_new_codes", True):
            self.newCodesFound.emit(result.new_items)
            names = "、".join(f"{it.game_name} {it.code}" for it in result.new_items[:3])
            more = f" 等 {len(result.new_items)} 个" if len(result.new_items) > 3 else ""
            self._notifier.notify("🎮 发现新兑换码", names + more)
        self._finish(ok=True, msg=f"发现 {len(result.new_items)} 个新码" if result.new_items else "已是最新")

    def _on_fetch_fail(self, err: str) -> None:
        log.warning("拉取失败: %s", err)
        if self._cfg.get("notify.on_fetch_error", False):
            today = today_str()
            if self._error_notified_day != today:  # 每天最多提醒一次，防打扰
                self._error_notified_day = today
                self._notifier.notify("数据暂时无法更新", "已继续使用本地缓存数据")
        self._finish(ok=False, msg=ERR_MSG)

    def _finish(self, ok: bool, msg: str) -> None:
        self._fetching = False
        self.fetchFinished.emit(ok, msg)
