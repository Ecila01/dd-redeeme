"""JsonFileCache 的 diff 与用户标记持久化单元测试（不依赖 Qt）。"""
from pathlib import Path

from code_widget.core.cache import JsonFileCache
from code_widget.core.models import STATUS_EXPIRED_LOCAL, STATUS_NONE, CodeItem


def _item(code: str, game_id: str = "genshin", expired: bool = False) -> CodeItem:
    return CodeItem(game_id=game_id, game_name="原神", code=code, expired_remote=expired)


def test_diff_detects_new_and_changed(tmp_path: Path):
    c = JsonFileCache(tmp_path / "cache.json")
    c.save_items([_item("A1"), _item("A2")])

    c2 = JsonFileCache(tmp_path / "cache.json")  # 模拟重启后加载
    result = c2.diff([_item("A2"), _item("A3"), _item("A1", expired=True)])
    assert [i.code for i in result.new_items] == ["A3"]
    assert [i.code for i in result.changed_items] == ["A1"]


def test_marks_survive_new_data(tmp_path: Path):
    c = JsonFileCache(tmp_path / "cache.json")
    c.save_items([_item("A1")])
    c.set_mark("genshin:A1", STATUS_EXPIRED_LOCAL)

    c.save_items([_item("A1"), _item("B1")])  # 新一轮拉取
    merged = {i.code: i for i in c.merge_marks(c.state.items)}
    assert merged["A1"].is_expired is True            # 本地标记仍在
    assert merged["B1"].user_status == STATUS_NONE    # 新条目无标记


def test_corrupt_cache_rebuilds(tmp_path: Path):
    p = tmp_path / "cache.json"
    p.write_text("{broken json", encoding="utf-8")
    c = JsonFileCache(p)
    assert c.state.items == []
    assert p.with_suffix(".json.bak").exists()        # 原文件已备份
