"""本地缓存与状态模块（F3/F7）：数据快照 + 用户标记 + diff + 损坏自愈。

user_marks 与快照分离存储：拉取新数据不会丢失用户标记。
所有写入均为原子写（临时文件 + replace）。
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from .models import STATUS_NONE, CodeItem, now_iso

log = logging.getLogger(__name__)

CACHE_SCHEMA_VERSION = 1


@dataclass
class CacheState:
    items: list[CodeItem] = field(default_factory=list)
    user_marks: dict = field(default_factory=dict)   # uid -> {"status": str, "marked_at": str}
    etags: dict = field(default_factory=dict)        # source_name -> etag
    last_fetch_at: str = ""
    last_daily_check: str = ""                       # YYYY-MM-DD（每日检查去重）


@dataclass
class DiffResult:
    new_items: list[CodeItem] = field(default_factory=list)      # 本次新增
    changed_items: list[CodeItem] = field(default_factory=list)  # expired_remote / rewards 变化


class BaseCache(ABC):
    @abstractmethod
    def load_state(self) -> CacheState: ...

    @abstractmethod
    def save_items(self, items: list[CodeItem], meta: dict | None = None) -> None: ...

    @abstractmethod
    def diff(self, items: list[CodeItem]) -> DiffResult: ...

    @abstractmethod
    def merge_marks(self, items: list[CodeItem]) -> list[CodeItem]: ...

    @abstractmethod
    def set_mark(self, uid: str, status: str | None) -> None:
        """status=None 表示清除标记。"""


class JsonFileCache(BaseCache):
    def __init__(self, path: Path):
        self.path = path
        self.state = CacheState()
        self.load_state()

    # ---------- IO ----------
    def load_state(self) -> CacheState:
        if not self.path.exists():
            return self.state
        try:
            doc = json.loads(self.path.read_text("utf-8"))
            self.state.items = [CodeItem.from_dict(d) for d in doc.get("snapshot", [])]
            self.state.user_marks = doc.get("user_marks", {})
            self.state.etags = doc.get("etags", {})
            self.state.last_fetch_at = doc.get("last_fetch_at", "")
            self.state.last_daily_check = doc.get("last_daily_check", "")
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as e:
            bak = self.path.with_suffix(".json.bak")
            log.error("缓存损坏(%s)，备份为 %s 后重建", e, bak)
            try:
                self.path.replace(bak)
            except OSError:
                pass
            self.state = CacheState()
        return self.state

    def _save(self) -> None:
        doc = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "last_fetch_at": self.state.last_fetch_at,
            "last_daily_check": self.state.last_daily_check,
            "etags": self.state.etags,
            "user_marks": self.state.user_marks,
            "snapshot": [it.to_dict() for it in self.state.items],
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), "utf-8")
            tmp.replace(self.path)
        except OSError as e:
            log.error("缓存写入失败: %s", e)

    # ---------- 业务 ----------
    def save_items(self, items: list[CodeItem], meta: dict | None = None) -> None:
        for it in items:
            if not it.first_seen:
                it.first_seen = now_iso()
        self.state.items = list(items)
        self.state.last_fetch_at = (meta or {}).get("last_fetch_at", now_iso())
        self._save()

    def diff(self, items: list[CodeItem]) -> DiffResult:
        old = {it.uid: it for it in self.state.items}
        result = DiffResult()
        for it in items:
            prev = old.get(it.uid)
            if prev is None:
                result.new_items.append(it)
            elif prev.expired_remote != it.expired_remote or prev.rewards != it.rewards:
                result.changed_items.append(it)
        return result

    def merge_marks(self, items: list[CodeItem]) -> list[CodeItem]:
        for it in items:
            mark = self.state.user_marks.get(it.uid) or {}
            it.user_status = mark.get("status", STATUS_NONE)
            it.marked_at = mark.get("marked_at", "")
        return items

    def set_mark(self, uid: str, status: str | None) -> None:
        if status is None or status == STATUS_NONE:
            self.state.user_marks.pop(uid, None)
        else:
            self.state.user_marks[uid] = {"status": status, "marked_at": now_iso()}
        for it in self.state.items:
            if it.uid == uid:
                it.user_status = status or STATUS_NONE
                it.marked_at = "" if status in (None, STATUS_NONE) else now_iso()
        self._save()

    def set_last_daily_check(self, day: str) -> None:
        self.state.last_daily_check = day
        self._save()
