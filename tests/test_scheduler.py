"""ms_until_next 每日定时计算单元测试（不依赖 Qt 运行循环）。"""
from datetime import datetime

from code_widget.core.scheduler import ms_until_next

H = 3600 * 1000
M = 60 * 1000


def test_same_day():
    now = datetime(2026, 9, 5, 10, 0, 0)
    assert ms_until_next("12:00", now) == 2 * H


def test_rolls_to_next_day_when_passed():
    now = datetime(2026, 9, 5, 13, 30, 0)
    assert ms_until_next("12:00", now) == (22 * H + 30 * M)


def test_exact_boundary_rolls_to_next_day():
    now = datetime(2026, 9, 5, 12, 0, 0)
    assert ms_until_next("12:00", now) == 24 * H


def test_midnight_cross():
    now = datetime(2026, 9, 5, 23, 59, 0)
    assert ms_until_next("00:00", now) == 1 * M
