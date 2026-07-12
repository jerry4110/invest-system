"""T-24 수용 기준: 기술 지표(순수 계산)·규칙 기반 시그널·수급/공매도 격리·API."""
from datetime import date, timedelta

import pytest

from backend.domain.technical import analyze_technical, rsi, sma


def _series(closes: list[float], start=None):
    start = start or date(2026, 1, 1)
    return [{"date": (start + timedelta(days=i)).isoformat(),
             "open": c * 0.99, "high": c * 1.01, "low": c * 0.98, "close": c,
             "volume": 1000} for i, c in enumerate(closes)]


def test_sma():
    assert sma([1, 2, 3, 4, 5], 5) == 3.0
    assert sma([1, 2, 3], 5) is None                     # 데이터 부족 → None (추정 금지)


def test_rsi_extremes():
    up = [100 + i for i in range(20)]                    # 연속 상승 → RSI 100
    down = [100 - i for i in range(20)]                  # 연속 하락 → RSI 0
    assert rsi(up, 14) == 100.0
    assert rsi(down, 14) == 0.0
    assert rsi([100, 101], 14) is None                   # 부족


def test_alignment_and_signal():
    """정배열 상승 추세 → 매수 시그널, 하락 추세 → 매도 시그널."""
    up = _series([100 * (1.01 ** i) for i in range(150)])
    r = analyze_technical(up)
    assert r["ma"]["5"] > r["ma"]["20"] > r["ma"]["60"] > r["ma"]["120"]
    assert r["ma_alignment"] == "정배열"
    assert r["signal"]["verdict"] == "매수"
    assert any("정배열" in reason for reason in r["signal"]["reasons"])

    down = _series([100 * (0.99 ** i) for i in range(150)])
    r2 = analyze_technical(down)
    assert r2["ma_alignment"] == "역배열"
    assert r2["signal"]["verdict"] == "매도"


def test_rsi_overbought_noted():
    up = _series([100 * (1.02 ** i) for i in range(150)])
    r = analyze_technical(up)
    assert r["rsi"] > 70
    assert any("과매수" in reason for reason in r["signal"]["reasons"])


def test_insufficient_data_handled():
    r = analyze_technical(_series([100, 101, 102]))
    assert r["ma"]["120"] is None
    assert r["signal"]["verdict"] == "판단 보류"          # 지표 부족 시 억지 판정 금지


def test_technical_api_with_flows_isolation(tmp_path, monkeypatch):
    """API 계약 + 수급/공매도 실패 격리 (국내 데이터 소스 장애가 분석을 막지 않음)."""
    from fastapi.testclient import TestClient
    from backend import main as main_mod
    from backend.infra import db as db_mod
    from backend.services import analysis_service

    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))

    closes = [100 * (1.005 ** i) for i in range(150)]
    monkeypatch.setattr(analysis_service, "_load_ohlcv", lambda t, days=180: _series(closes))
    monkeypatch.setattr(analysis_service, "_load_investor_flows",
                        lambda t: (_ for _ in ()).throw(ConnectionError("KRX down")))
    monkeypatch.setattr(analysis_service, "_load_short_interest", lambda t: [
        {"date": "2026-07-10", "balance": 1000, "ratio_pct": 0.5}])

    body = TestClient(main_mod.create_app()).get("/api/analysis/technical/005930").json()
    assert body["signal"]["verdict"] in ("매수", "중립", "매도", "판단 보류")
    assert body["rsi"] is not None and body["as_of"]
    assert body["investor_flows"] is None                 # 실패 → None + 사유
    assert "KRX" in body["notes"][0]
    assert body["short_interest"][0]["ratio_pct"] == 0.5
    assert len(body["ohlcv"]) > 0                         # 차트용 데이터 포함
