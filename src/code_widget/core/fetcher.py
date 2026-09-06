"""数据获取模块（F2/F12）。

抽象 BaseFetcher → 当前实现 GitHubRawFetcher（UA/超时/3次退避重试/ETag 条件请求）
与 FailoverFetcher（按配置顺序多源回退）。未来可扩展 APIFetcher / LocalFileFetcher。
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests

from .. import __version__
from .models import now_iso

log = logging.getLogger(__name__)

USER_AGENT = f"DD-RedeeMe/{__version__} (+https://github.com/Ecila01/dd-redeeme)"


class FetchError(Exception):
    """拉取失败（网络 / HTTP / 全部源失败）。"""


class NotModified(FetchError):
    """304：数据无更新。不算错误，Service 据此跳过解析。"""


@dataclass
class RawPayload:
    body: bytes
    source_name: str
    url: str
    fetched_at: str
    etag: str | None = None


class BaseFetcher(ABC):
    @abstractmethod
    def fetch(self) -> RawPayload:
        """拉取原始数据；失败抛 FetchError，304 抛 NotModified。超时与重试由实现内部负责。"""

    @abstractmethod
    def name(self) -> str: ...


class GitHubRawFetcher(BaseFetcher):
    def __init__(self, url: str, name_: str, timeout: int = 10,
                 max_retries: int = 3, etag_store: dict | None = None):
        self._url, self._name = url, name_
        self._timeout, self._retries = timeout, max(1, max_retries)
        self._etag_store = etag_store if etag_store is not None else {}
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT

    def name(self) -> str:
        return self._name

    def fetch(self) -> RawPayload:
        headers = {}
        if etag := self._etag_store.get(self._name):
            headers["If-None-Match"] = etag
        last_err: Exception = ConnectionError("未发起请求")
        for attempt in range(self._retries):
            try:
                resp = self._session.get(self._url, timeout=self._timeout, headers=headers)
                if resp.status_code == 304:
                    raise NotModified(f"[{self._name}] 304 数据无更新")
                resp.raise_for_status()
                etag = resp.headers.get("ETag")
                if etag:
                    self._etag_store[self._name] = etag
                log.info("[%s] 拉取成功 %d bytes", self._name, len(resp.content))
                return RawPayload(resp.content, self._name, self._url, now_iso(), etag)
            except NotModified:
                raise
            except requests.RequestException as e:
                last_err = e
                log.warning("[%s] 第 %d/%d 次失败: %s", self._name, attempt + 1, self._retries, e)
                if attempt < self._retries - 1:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s 退避
        raise FetchError(f"[{self._name}] 重试 {self._retries} 次仍失败: {last_err}")


class FailoverFetcher(BaseFetcher):
    """组合多个数据源，按序尝试；一个成功即返回，全部失败抛聚合 FetchError。"""

    def __init__(self, fetchers: list[BaseFetcher]):
        if not fetchers:
            raise FetchError("未配置任何可用数据源")
        self._fetchers = fetchers

    def name(self) -> str:
        return "failover(" + ",".join(f.name() for f in self._fetchers) + ")"

    def fetch(self) -> RawPayload:
        errs: list[str] = []
        for f in self._fetchers:
            try:
                return f.fetch()
            except NotModified:
                raise
            except FetchError as e:
                errs.append(str(e))
                log.warning("数据源 %s 失败，尝试下一个", f.name())
        raise FetchError("所有数据源均失败:\n" + "\n".join(errs))


def build_fetchers_from_config(cfg, etag_store: dict) -> FailoverFetcher:
    """工厂：cfg.data_sources → Fetcher 组合。新增数据源类型在此注册即可，无需改 Service。"""
    fetchers: list[BaseFetcher] = []
    for src in cfg.get("data_sources", []) or []:
        if not src.get("enabled", True):
            continue
        kind = src.get("type")
        if kind == "github_raw":
            fetchers.append(GitHubRawFetcher(
                url=src["url"],
                name_=src.get("name", src["url"]),
                timeout=cfg.get("fetch.timeout_seconds", 10),
                max_retries=cfg.get("fetch.max_retries", 3),
                etag_store=etag_store,
            ))
        else:
            # 扩展点：注册 rest_api / local_file 等新 Fetcher 类型
            log.warning("未知数据源类型 %r，已跳过", kind)
    return FailoverFetcher(fetchers)
