"""T-07 수용 기준: 보유현황 조회(비중·합계·as_of), 예수금, CSV 내보내기."""
import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod

CSV = """종목명,종목코드,보유수량,매입평균가,매입금액,현재가,평가금액,평가손익,수익률
삼성전자,005930,100,70000,7000000,75000,7500000,500000,7.14
카카오,035720,50,40000,2000000,50000,2500000,500000,25.0
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


def test_holdings_with_weight_and_totals(client):
    body = client.get("/api/portfolio/holdings").json()
    assert len(body["holdings"]) == 2
    samsung = next(h for h in body["holdings"] if h["name"] == "삼성전자")
    assert samsung["weight_pct"] == 75.0                    # 7.5M / 10M (FR-03-13)
    assert body["totals"]["eval_amount"] == 10000000
    assert body["totals"]["pnl_amount"] == 1000000
    assert body["as_of"]                                     # NFR-04
    assert body["holdings"][0]["account"]                    # 계좌별 표시 (FR-03-11)


def test_cash_roundtrip(client):
    """예수금 수기 입력 (FR-03-04·11)."""
    r = client.put("/api/portfolio/cash", json={"amount": 3000000})
    assert r.status_code == 200
    body = client.get("/api/portfolio/holdings").json()
    assert body["totals"]["cash"] == 3000000
    assert body["totals"]["total_asset"] == 13000000         # 평가금액 + 예수금


def test_cash_rejects_negative(client):
    assert client.put("/api/portfolio/cash", json={"amount": -1}).status_code == 422


def test_csv_export(client):
    """FR-03-14: 현황 CSV 내보내기."""
    r = client.get("/api/portfolio/export.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    text = r.content.decode("utf-8-sig")
    assert "삼성전자" in text and "카카오" in text
    assert text.splitlines()[0].startswith("계좌,종목명")


def test_empty_portfolio_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "e.db"))
    body = TestClient(main_mod.create_app()).get("/api/portfolio/holdings").json()
    assert body["holdings"] == [] and body["totals"]["total_asset"] == 0
