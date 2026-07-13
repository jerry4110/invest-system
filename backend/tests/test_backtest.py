"""T-32 수용 기준: 성과지표(알려진 수치 예제), 가격 파일 파싱, 시나리오 저장·차트."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.domain.backtest import metrics_from_equity, trade_stats
from backend.infra import db as db_mod


def _curve(values, start=date(2024, 1, 1), step_days=1):
    return ([start + timedelta(days=i * step_days) for i in range(len(values))], values)


def test_cumulative_and_cagr_known_example():
    """100→200, 정확히 2년(730일) → 누적 100%, CAGR = √2-1 ≈ 41.42%."""
    dates = [date(2024, 1, 1), date(2025, 12, 31)]   # 정확히 730일 = 2.0년
    m = metrics_from_equity(dates, [100.0, 200.0])
    assert m["cumulative_return_pct"] == 100.0
    assert m["cagr_pct"] == pytest.approx(41.42, abs=0.05)


def test_mdd_and_mar():
    """100→120→90→180: MDD = (120-90)/120 = 25%."""
    dates, values = _curve([100, 120, 90, 180], step_days=180)
    m = metrics_from_equity(dates, values)
    assert m["mdd_pct"] == 25.0
    assert m["mar"] == pytest.approx(m["cagr_pct"] / 25.0, abs=0.01)


def test_flat_series_edge():
    dates, values = _curve([100, 100, 100])
    m = metrics_from_equity(dates, values)
    assert m["cumulative_return_pct"] == 0.0
    assert m["mdd_pct"] == 0.0
    assert m["sharpe"] is None                             # 변동 없음 → 산출 불가 (추정 금지)


def test_trade_stats():
    s = trade_stats([{"pnl_pct": 10}, {"pnl_pct": -5}, {"pnl_pct": 20}, {"pnl_pct": -5}])
    assert s["win_rate_pct"] == 50.0
    assert s["payoff_ratio"] == pytest.approx(3.0)          # 평균이익 15 / 평균손실 5
    assert s["trades"] == 4


def test_price_file_parse(tmp_path):
    """FR-07-01: 날짜·가격 컬럼 자동 감지, 콤마·잡음 행 허용."""
    from backend.adapters.market.price_file import parse_price_file
    csv = """조회기간: 2024-01-01 ~ ,
일자,종가,거래량
2024-01-02,"2,655.28",1000
2024-01-03,"2,607.31",1200
2024-01-04,"2,587.02",900
"""
    p = tmp_path / "kospi.csv"
    p.write_text(csv, encoding="utf-8-sig")
    dates, values = parse_price_file(p)
    assert len(values) == 3 and values[0] == pytest.approx(2655.28)
    assert dates[0].isoformat() == "2024-01-02"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    return TestClient(main_mod.create_app())


def test_upload_backtest_api(client):
    csv = "일자,종가\n" + "\n".join(
        f"2024-{m:02d}-01,{100 + m * 5}" for m in range(1, 13))
    r = client.post("/api/backtest/upload", data={"name": "코스피 테스트"},
                    files={"file": ("prices.csv", csv.encode("utf-8-sig"), "text/csv")})
    assert r.status_code == 200
    body = r.json()
    for k in ("cumulative_return_pct", "cagr_pct", "mdd_pct", "mar", "sharpe"):
        assert k in body["metrics"]
    assert len(body["curve"]) == 12                         # 프론트 SVG용
    assert "수수료" in body["disclaimer"]                    # 미반영 고지

    runs = client.get("/api/backtest/runs").json()          # FR-07-05 시나리오 저장
    assert len(runs) == 1 and runs[0]["name"] == "코스피 테스트"

    png = client.get(f"/api/backtest/runs/{runs[0]['id']}/chart.png")   # FR-07-04 정적
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    assert png.content[:4] == b"\x89PNG"
