"""CodesJsonParser 单元测试（不依赖 Qt）。"""
import json

import pytest

from code_widget.core.fetcher import RawPayload
from code_widget.core.models import STATUS_NONE
from code_widget.core.parser import CodesJsonParser, ParseError

DOC = {
    "schema_version": 1,
    "updated_at": "2026-09-01T12:00:00+08:00",
    "games": [
        {
            "id": "genshin",
            "name": "原神",
            "codes": [
                {"code": "ab 12", "rewards": "原石×60", "source": "前瞻", "expired": False},
                {"rewards": "缺 code，应被跳过"},
            ],
        },
        {"id": "zzz", "name": "绝区零", "codes": []},
        {"name": "缺少 id 的游戏，整节点跳过", "codes": [{"code": "X1"}]},
    ],
}


def _payload(doc) -> RawPayload:
    return RawPayload(json.dumps(doc).encode("utf-8"), "test", "mem://test",
                      "2026-09-01T00:00:00+08:00")


def test_parse_normalizes_and_skips_bad_entries():
    items = CodesJsonParser().parse(_payload(DOC))
    assert len(items) == 1
    it = items[0]
    assert it.uid == "genshin:AB12"          # 空格剔除 + 大写归一化
    assert it.game_name == "原神"
    assert it.user_status == STATUS_NONE
    assert it.is_expired is False


def test_missing_games_raises():
    with pytest.raises(ParseError):
        CodesJsonParser().parse(_payload({"foo": 1}))


def test_bad_json_raises():
    with pytest.raises(ParseError):
        CodesJsonParser().parse(RawPayload(b"{not json", "t", "m", "x"))
