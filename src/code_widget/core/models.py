"""统一数据模型：所有模块只传递 CodeItem，与远程 JSON 结构解耦（F13-5）。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime

# 用户本地标记状态（仅存于本地 cache.json，不回写远程仓库，F7）
STATUS_NONE = "none"
STATUS_REDEEMED = "redeemed"              # 已兑换
STATUS_EXPIRED_LOCAL = "expired_local"    # 本地标记过期


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


@dataclass
class CodeItem:
    """兑换码统一模型。

    过期语义（需求明确）：过期 = 远程维护者标记(expired_remote) ∪ 用户本地标记，
    永不根据 expires_at 自动推断；expires_at 仅用于展示。
    """

    game_id: str              # genshin / hsr / ww / zzz
    game_name: str            # 原神 / 崩坏：星穹铁道 / 鸣潮 / 绝区零
    code: str
    source: str = ""          # 如 "5.0 版本前瞻特别节目"
    rewards: str = ""
    published_at: str = ""    # YYYY-MM-DD
    expires_at: str = ""      # YYYY-MM-DD，空 = 未知
    expired_remote: bool = False
    note: str = ""
    # ---- 以下字段由本地生成，不属于远程数据 ----
    user_status: str = STATUS_NONE
    marked_at: str = ""
    first_seen: str = ""      # 本地首次发现时间

    @property
    def uid(self) -> str:
        """全局唯一键：缓存 diff 与本地标记索引。"""
        return f"{self.game_id}:{self.code}"

    @property
    def is_expired(self) -> bool:
        return self.expired_remote or self.user_status == STATUS_EXPIRED_LOCAL

    @property
    def is_redeemed(self) -> bool:
        return self.user_status == STATUS_REDEEMED

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CodeItem":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})
