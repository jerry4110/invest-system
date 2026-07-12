"""T-08 수용 기준: 자산 요약(FR-02-01), 전일 대비(FR-02-02), 구성비(FR-02-03), 스냅샷."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod
from backend.infra.schema import AssetSnapshot

CSV = """종목명,종목코드,보유수량,매입평균가,매입금액,현재가,평가금액,평가손익,수익률
삼성전자,005930,100,70000,7000000,75000,7500000,500000,7.14
NVIDIA,NVDA,10,120,1200000,180,2500000,1300000,108.3
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    c = TestClient(main_mod.create_app())
    c.post("/api/portfolio/upload",
           files={"file": ("잔고.csv", CSV.encode("utf-8-sig"), "text/csv")})
    c.put("/api/portfolio/cash", json={"amount": 2000000})
    return c


def test_summary_totals_and_snapshot(client):
    body = client.get("/api/dashboard/summary").json()
    assert body["total_asset"] == 12000000          # 10M 평가 + 2M 예수금
    assert body["total_eval"] == 10000000
    assert body["total_cash"] == 2000000
    assert body["as_of"]                            # NFR-04
    # 업로드·예수금 반영 시 오늘 스냅샷 자동 기록 (FR-02-02 기반)
    with db_mod.get_session() as s:
        snap = s.query(AssetSnapshot).filter_by(date=date.today()).one()
        assert float(snap.total_asset) == 12000000


def test_day_change_vs_yesterday(client):
    with db_mod.get_session() as s:
        s.add(AssetSnapshot(date=date.today() - timedelta(days=1),
                            total_asset=11000000, total_buy=10200000,
                            total_eval=9500000, total_pnl=-700000, total_cash=1500000))
        s.commit()
    body = client.get("/api/dashboard/summary").json()
    assert body["day_change"]["amount"] == 1000000   # 12M - 11M
    assert body["day_change"]["pct"] == 9.09


def test_composition_sums_to_100(client):
    body = client.get("/api/dashboard/summary").json()
    comp = {c["label"]: c["pct"] for c in body["composition"]}
    assert set(comp) == {"국내주식", "해외주식", "현금"}
    assert round(sum(comp.values()), 1) == 100.0
    assert comp["현금"] == round(2000000 / 12000000 * 100, 2)


def test_empty_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "e.db"))
    body = TestClient(main_mod.create_app()).get("/api/dashboard/summary").json()
    assert body["total_asset"] == 0 and body["day_change"] is None
