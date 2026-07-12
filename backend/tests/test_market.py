"""T-03 수용 기준: 10개 지표 레지스트리, 수집·업서트, 재시도·폴백 격리."""
from datetime import date, datetime, timedelta

import pytest

from backend.adapters.market.indicators import INDICATORS
from backend.services import market_service
from backend.infra import db as db_mod
from backend.infra.schema import MarketIndicator


@pytest.fixture()
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    return db_mod.get_session


def test_registry_has_10_indicators():
    """FR-02-11~12: 지수 5종 + 거시 5종."""
    expected = {"KOSPI", "KOSDAQ", "NASDAQ", "SP500", "DOW",
                "USDKRW", "WTI", "GOLD", "BTC", "UST10Y"}
    assert expected == set(INDICATORS.keys())
    for code, spec in INDICATORS.items():
        assert spec.name and spec.symbol  # 이름·벤더 심볼 필수


def _fake_series(base: float):
    today = date.today()
    return [(today - timedelta(days=i), base + i) for i in range(29, -1, -1)]


def test_collect_upserts_with_as_of(session):
    fetchers = {code: (lambda b=i: _fake_series(100.0 * (b + 1)))
                for i, code in enumerate(INDICATORS)}
    result = market_service.collect_all(fetchers=fetchers)
    assert result["ok"] == 10 and result["failed"] == []
    with session() as s:
        rows = s.query(MarketIndicator).filter_by(code="KOSPI").all()
        assert len(rows) == 30
        assert all(isinstance(r.as_of, datetime) for r in rows)  # NFR-04
    # 재수집 시 중복 없이 업서트
    market_service.collect_all(fetchers=fetchers)
    with session() as s:
        assert s.query(MarketIndicator).filter_by(code="KOSPI").count() == 30


def test_change_pct_computed(session):
    fetchers = {code: (lambda: _fake_series(100.0)) for code in INDICATORS}
    market_service.collect_all(fetchers=fetchers)
    latest = market_service.get_latest()
    kospi = next(x for x in latest if x["code"] == "KOSPI")
    # 마지막 이틀: 101 -> 100 → -0.99%
    assert kospi["value"] == 100.0
    assert round(kospi["change_pct"], 2) == -0.99


def test_failure_isolated_and_old_data_kept(session):
    good = {code: (lambda: _fake_series(100.0)) for code in INDICATORS}
    market_service.collect_all(fetchers=good)

    calls = {"n": 0}
    def boom():
        calls["n"] += 1
        raise ConnectionError("network down")
    bad = dict(good)
    bad["WTI"] = boom
    result = market_service.collect_all(fetchers=bad)
    assert result["ok"] == 9
    assert "WTI" in result["failed"]          # FR-00-08 실패 격리
    assert calls["n"] == 3                     # 3회 재시도
    with session() as s:                       # 기존 데이터 유지
        assert s.query(MarketIndicator).filter_by(code="WTI").count() == 30
