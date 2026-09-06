"""数据解析模块：RawPayload(JSON bytes) → list[CodeItem]。

容错策略：顶层缺 games 抛 ParseError；单条记录缺 code 跳过该条（记日志）；
未知字段忽略；schema_version 高于已知版本时警告但尽力解析（向前兼容）。
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

from .fetcher import RawPayload
from .models import STATUS_NONE, CodeItem

log = logging.getLogger(__name__)

SUPPORTED_SCHEMA_VERSION = 1


class ParseError(Exception):
    """整体解析失败（与"跳过单条"区分）。"""


class BaseParser(ABC):
    @abstractmethod
    def parse(self, raw: RawPayload) -> list[CodeItem]: ...


class CodesJsonParser(BaseParser):
    def parse(self, raw: RawPayload) -> list[CodeItem]:
        try:
            doc = json.loads(raw.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ParseError(f"JSON 解析失败: {e}") from e

        games = doc.get("games")
        if not isinstance(games, list):
            raise ParseError("数据缺少 games 数组，不符合 codes.json 契约")

        version = doc.get("schema_version", 1)
        if version > SUPPORTED_SCHEMA_VERSION:
            log.warning("schema_version=%s 高于已支持版本 %s，尽力解析",
                        version, SUPPORTED_SCHEMA_VERSION)

        items: list[CodeItem] = []
        valid_games = 0
        for gi, game in enumerate(games):
            gid = str(game.get("id", "")).strip()
            gname = str(game.get("name", gid)).strip()
            if not gid:
                log.warning("第 %d 个游戏节点缺少 id，跳过", gi)
                continue
            valid_games += 1
            for ci, entry in enumerate(game.get("codes") or []):
                try:
                    code = str(entry["code"]).replace(" ", "").upper()
                    if not code:
                        raise KeyError("code 为空")
                except (KeyError, TypeError) as e:
                    log.warning("%s 第 %d 条记录无效(%s)，跳过", gid, ci, e)
                    continue
                items.append(CodeItem(
                    game_id=gid,
                    game_name=gname,
                    code=code,
                    source=str(entry.get("source", "")),
                    rewards=str(entry.get("rewards", "")),
                    published_at=str(entry.get("published_at", "")),
                    expires_at=str(entry.get("expires_at", "")),
                    expired_remote=bool(entry.get("expired", False)),
                    note=str(entry.get("note", "")),
                    user_status=STATUS_NONE,
                ))
        log.info("解析完成：%d 个游戏 / %d 条兑换码", valid_games, len(items))
        return items
