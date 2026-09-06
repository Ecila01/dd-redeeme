"""配置集中管理（F11）：DEFAULTS + config.json 深合并 + 原子保存。

- 缺失键自动补默认值（向后兼容）；文件损坏转 .bak 后重建。
- 打包(frozen)后配置在 exe 同目录、缓存在 %APPDATA%/DDRedeeMe；
  开发模式两者都在仓库根目录。绝不允许写 sys._MEIPASS（临时目录会蒸发）。
"""
from __future__ import annotations

import copy
import json
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULTS: dict = {
    "general": {"autostart": True, "language": "zh-CN",
                "repo_url": "https://github.com/Ecila01/game-codes-repo"},
    "data_sources": [
        {
            "name": "github-primary",
            "type": "github_raw",
            "url": "https://raw.githubusercontent.com/Ecila01/game-codes-repo/main/codes.json",
            "enabled": True,
        },
        {
            "name": "jsdelivr-mirror",
            "type": "github_raw",
            "url": "https://cdn.jsdelivr.net/gh/Ecila01/game-codes-repo@main/codes.json",
            "enabled": True,
        },
    ],
    "fetch": {
        "interval_minutes": 30,
        "timeout_seconds": 10,
        "max_retries": 3,
        "daily_check_time": "12:00",
        "check_on_startup": True,
    },
    "notify": {
        "enabled": True,
        "on_new_codes": True,
        "on_fetch_error": False,
        "daily_summary": True,
    },
    "ui": {
        "opacity": 0.95,
        "scale": 1.0,
        "always_on_top": True,
        "snap_enabled": True,
        "snap_threshold_px": 24,
        "edge_margin_px": 8,
        "compact_visible_count": 3,
        "bubble_seconds": 5,
        "expanded_size": [380, 580]
    },
    "cache": {"max_expired_days": 30},
}


def app_dirs() -> tuple[Path, Path]:
    """返回 (配置目录, 缓存目录)。"""
    if getattr(sys, "frozen", False):  # PyInstaller 打包
        cfg_dir = Path(sys.executable).resolve().parent
        cache_dir = Path.home() / "AppData" / "Roaming" / "DDRedeeMe"
    else:  # 开发模式：仓库根目录
        base = Path(__file__).resolve().parents[3]
        cfg_dir, cache_dir = base, base / "cache"
    return cfg_dir, cache_dir


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class ConfigManager:
    def __init__(self, path: Path | None = None):
        cfg_dir, cache_dir = app_dirs()
        self.path = path or cfg_dir / "config.json"
        self.cache_dir = cache_dir
        self.data: dict = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            log.warning("配置不存在，生成默认配置: %s", self.path)
            self.save()
            return
        try:
            user = json.loads(self.path.read_text("utf-8"))
            self.data = _deep_merge(DEFAULTS, user)
        except (json.JSONDecodeError, OSError) as e:
            bak = self.path.with_suffix(".json.bak")
            log.error("配置损坏(%s)，备份为 %s 后重建", e, bak)
            try:
                self.path.replace(bak)
            except OSError:
                pass
            self.data = copy.deepcopy(DEFAULTS)
            self.save()

    def get(self, dotted: str, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), "utf-8")
            tmp.replace(self.path)
        except OSError as e:
            log.error("配置写入失败: %s", e)
