"""T-33 수용 기준: 채널 계산·돌파 진입/청산·스탑로스·오늘 시그널·배치 알림 (FR-07-11~15)."""
from datetime import date, timedelta

import pytest

from backend.domain.donchian import analyze_today, donchian_channels, generate_positions
from backend.infra import db as db_mod


def _bars(closes, highs=None, lows=None, start=date(2026, 1, 1)):
    return [{"date": (start + timedelta(days=i)).isoformat(),
             "open": c, "high": (highs[i] if highs else c),
             "low": (lows[i] if lows else c), "close": c, "volume": 1000}
            for i, c in enumerate(closes)]


def test_channels_known_values():
    """직전 N일(당일 제외) 최고/최저."""
    bars = _bars([10, 20, 15, 30, 25])
    upper, lower = donchian_channels(bars, n=3)
    assert upper[4] == 30 and lower[4] == 15      # 직전 3일: 20,15,30 → 상단30? 아니 15,30,25?
