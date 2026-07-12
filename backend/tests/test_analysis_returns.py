"""T-29 수용 기준: 투자유형·산업 분류, 기간 수익률·벤치마크, 자산 추이."""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod
from backend.infra.schema import AssetSnapshot, MarketIndicator

CSV = """종목코드,종목명,카테고리,지역,보유수량,평균매입가,현재가,매입금액,평가금액,평가손익,수익률
455850,SOL AI반도체소부장,반도체,국내,540,22489,33230,12144130,17944200,5800070,47.76%
005930,삼성전자,반도체,국내,100,70000,75000,7000000,7500000,500000,7.14%
NVDA,엔비디아,반도체,해외,10,120,180,1200000,1800000,600000,50%
486450,SOL 미국AI전력인프라,전력,기타,369,18730,25540,6911230,9424260,2513030,36.36%
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    c = TestClient(main_mod.create_app())
    c.post("/api/portfolio/upload",
           files={"file": ("잔고.csv", CSV.encode("utf-8-sig"), "text/csv")})
    return c


def test_classification_by_type_and_sector(client):
    """FR-03-22~23: 투자유형(ETF/개별·국내/해외) + 산업(파일 '카테고리' 초기값)."""
    body = client.get("/api/portfolio/analysis").json()
    types = {t["label"]: t["eval_amount"] for t in body["by_type"]}
    assert types["국내 ETF"] == 17944200 + 9424260      # SOL 2종
    assert types["국내 주식"] == 7500000                 # 삼성전자
    assert types["해외 주식"] == 1800000                 # NVDA
    sectors = {x["label"]: x["eval_amount"] for x in body["by_sector"]}
    assert sectors["반도체"] == 17944200 + 7500000 + 1800000
    assert sectors["전력"] == 9424260
    assert body["as_of"]                                  # NFR-04


def test_period_returns_with_benchmark(client):
    """FR-03-24~25: 스냅샷 기간 수익률 + 코스피 벤치마크 비교."""
    today = date.today()
    with db_mod.get_session() as s:
        s.query(AssetSnapshot).delete()
        for days, asset in ((30, 100_000_000), (7, 105_000_000), (0, 110_250_000)):
            s.add(AssetSnapshot(date=today - timedelta(days=days), total_asset=asset,
                                total_buy=0, total_eval=asset, total_pnl=0, total_cash=0))
        for days, val in ((30, 3000.0), (7, 3100.0), (0, 3100.0)):
            s.add(MarketIndicator(code="KOSPI", name="코스피", date=today - timedelta(days=days),
                                  value=val, change_pct=0, as_of=datetime.now()))
        s.commit()
    body = client.get("/api/portfolio/returns").json()
    r = {x["period"]: x for x in body["returns"]}
    assert r["1w"]["portfolio_pct"] == 5.0                # 105M → 110.25M
    assert r["1m"]["portfolio_pct"] == 10.25              # 100M → 110.25M
    assert r["1w"]["benchmark_pct"] == 0.0                # 코스피 3100 → 3100
    assert round(r["1m"]["benchmark_pct"], 2) == 3.33     # 3000 → 3100
    assert r["1m"]["excess_pct"] == round(10.25 - r["1m"]["benchmark_pct"], 2)


def test_trend_series(client):
    """FR-03-26: 자산 추이 시계열."""
    today = date.today()
    with db_mod.get_session() as s:
        s.query(AssetSnapshot).delete()
        for d in range(5):
            s.add(AssetSnapshot(date=today - timedelta(days=d), total_asset=100 + d,
                                total_buy=0, total_eval=0, total_pnl=0, total_cash=0))
        s.commit()
    body = client.get("/api/portfolio/trend").json()
    assert len(body) == 5
    assert body[0]["date"] < body[-1]["date"]              # 오름차순
    assert all("total_asset" in x for x in body)
