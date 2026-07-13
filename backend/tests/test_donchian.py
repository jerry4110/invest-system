"""T-33 수용 기준: 채널 계산·돌파 진입/청산·스탑로스·오늘 시그널·배치 알림 (FR-07-11~15)."""
from datetime import date, timedelta

import pytest

from backend.domain.donchian import analyze_today, donchian_channels, generate_positions
from backend.infra import db as db_mod


def _bars(closes, start=date(2026, 1, 1)):
    return [{"date": (start + timedelta(days=i)).isoformat(),
             "open": c, "high": c, "low": c, "close": c, "volume": 1000}
            for i, c in enumerate(closes)]


def test_channels_known_values():
    """채널 = 직전 N일(당일 제외) 최고/최저."""
    bars = _bars([10, 20, 15, 30, 25])
    upper, lower = donchian_channels(bars, n=3)
    assert upper[4] == 30 and lower[4] == 15      # 직전 3일: 20,15,30
    assert upper[2] is None                        # 데이터 부족 구간은 None


def test_breakout_entry_exit_and_stop():
    """상단 돌파 매수 → 스탑로스 우선 청산."""
    closes = [100.0] * 25 + [110, 115, 120, 118, 90]
    pos = generate_positions(_bars(closes), entry_n=20, exit_n=10, stop_pct=8.0)
    assert pos[24] == 0                            # 돌파 전 무포지션
    assert pos[25] == 1                            # 110 > 직전 20일 고점(100) → 진입
    assert pos[28] == 1                            # 보유 유지
    assert pos[29] == 0                            # 90: 진입가 110 대비 -18% → 스탑 청산


def test_analyze_today_signals():
    flat = [100.0] * 30
    assert analyze_today(_bars(flat + [112]), entry_n=20)["signal"] == "BUY"
    assert analyze_today(_bars(flat + [88]), entry_n=20)["signal"] == "SELL"
    r = analyze_today(_bars(flat + [100]), entry_n=20)
    assert r["signal"] is None and r["upper"] == 100 and r["lower"] == 100


def test_daily_check_creates_alert_once(tmp_path, monkeypatch):
    """FR-07-14: 코스피 일일 감시 → 시그널 알림 1회 (중복 방지)."""
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    from backend.infra.schema import Alert
    from backend.services import donchian_service

    monkeypatch.setattr(donchian_service, "_load_kospi",
                        lambda days=80: _bars([100.0] * 30 + [112]))
    assert donchian_service.daily_check()["signal"] == "BUY"
    donchian_service.daily_check()
    with db_mod.get_session() as s:
        alerts = s.query(Alert).filter_by(kind="donchian").all()
        assert len(alerts) == 1 and "매수" in alerts[0].title


def test_batch_isolates_donchian_failure(tmp_path, monkeypatch):
    """배치 통합: Donchian 실패가 배치 전체를 막지 않음 (FR-00-08)."""
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    from datetime import date as d2, timedelta as td
    from backend.adapters.market.indicators import INDICATORS
    from backend.jobs import morning_refresh
    from backend.services import donchian_service

    def fake_series(base=100.0):
        today = d2.today()
        return [(today - td(days=i), base + i) for i in range(29, -1, -1)]
    monkeypatch.setattr(donchian_service, "daily_check",
                        lambda: (_ for _ in ()).throw(ConnectionError("yahoo down")))
    result = morning_refresh.run(fetchers={c: fake_series for c in INDICATORS})
    assert result["status"] == "partial"
    assert "Donchian" in result["message"]


def test_donchian_backtest_api(tmp_path, monkeypatch):
    """FR-07-11·13: 파라미터 조정 백테스트 + 시나리오 저장."""
    from fastapi.testclient import TestClient

    from backend import main as main_mod
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    from backend.services import donchian_service

    closes = ([100.0] * 25 + [110, 115, 120, 125, 130]
              + [130 - i * 2 for i in range(1, 11)])
    monkeypatch.setattr(donchian_service, "_load_ohlcv",
                        lambda t, days: _bars(closes))
    client = TestClient(main_mod.create_app())
    r = client.post("/api/donchian/backtest",
                    json={"ticker": "KOSPI", "entry_n": 20, "exit_n": 10, "stop_pct": 8})
    assert r.status_code == 200
    body = r.json()
    assert body["metrics"]["trades"] >= 1
    assert "수수료" in body["disclaimer"]
    assert client.get("/api/backtest/runs").json()[0]["strategy"] == "donchian"
