"""투자저널 개선 (2026-07-15) — 매매 집계 형식·브로커 손익 보존·기간 조회·선택 삭제."""
import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod

AGG_CSV = """일자,종목명,기간 중 매수,,,기간 중 매도,,,매매비용,손익금액,수익률
,,수량,평균단가,매수금액,수량,평균단가,매도금액,,,
2026/07/13,삼성전자,15,266000,3990000,0,0,0,0,0,0.00
2026/06/26,솔브레인,0,0,0,6,332000,1992000,4587,-632016,-24.09
2026/05/12,두산에너빌리티,100,60000,6000000,0,0,0,0,0,0
2026/05/20,두산에너빌리티,0,0,0,50,70000,3500000,3000,497000,16.57
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    return TestClient(main_mod.create_app())


def _upload(client, text=AGG_CSV, name="주식계좌 5702 매매.csv"):
    return client.post("/api/journal/upload",
                       files={"file": (name, text.encode("cp949"), "text/csv")})


def test_aggregate_format_parsed(client):
    r = _upload(client)
    assert r.status_code == 200 and r.json()["imported"] == 4
    txs = client.get("/api/journal/transactions").json()
    assert len(txs) == 4
    buy = next(t for t in txs if t["ticker"] == "삼성전자")
    assert buy["side"] == "buy" and buy["qty"] == 15 and buy["price"] == 266000
    assert buy["amount"] == 15 * 266000                    # 신규 금액 컬럼
    assert buy["executed_at"].startswith("2026-07-13")


def test_broker_pnl_preserved(client):
    """증권사 계산 손익(매매비용 반영)은 재계산으로 덮지 않는다 — 매수 이력 없어도 유지."""
    _upload(client)
    txs = client.get("/api/journal/transactions").json()
    sol = next(t for t in txs if t["ticker"] == "솔브레인")
    assert sol["side"] == "sell" and sol["realized_pnl"] == -632016
    doo = next(t for t in txs if t["ticker"] == "두산에너빌리티" and t["side"] == "sell")
    assert doo["realized_pnl"] == 497000


def test_reupload_appends_without_duplicates(client):
    _upload(client)
    _upload(client)
    assert len(client.get("/api/journal/transactions").json()) == 4
    extra = AGG_CSV + "2026/07/14,LS,3,300000,900000,0,0,0,0,0,0\n"
    r = _upload(client, extra)
    assert r.json()["imported"] == 1
    assert len(client.get("/api/journal/transactions").json()) == 5


def test_date_range_filter_and_stats(client):
    _upload(client)
    txs = client.get("/api/journal/transactions?date_from=2026-06-01&date_to=2026-06-30").json()
    assert len(txs) == 1 and txs[0]["ticker"] == "솔브레인"

    s_all = client.get("/api/journal/stats").json()
    assert s_all["sell_count"] == 2
    assert s_all["total_realized_pnl"] == -632016 + 497000
    assert s_all["win_rate_pct"] == 50.0

    s_may = client.get("/api/journal/stats?date_from=2026-05-01&date_to=2026-05-31").json()
    assert s_may["sell_count"] == 1
    assert s_may["total_realized_pnl"] == 497000
    assert s_may["win_rate_pct"] == 100.0


def test_bulk_delete(client):
    _upload(client)
    txs = client.get("/api/journal/transactions").json()
    ids = [t["id"] for t in txs if t["ticker"] == "삼성전자"]
    r = client.request("DELETE", "/api/journal/transactions", json={"ids": ids})
    assert r.status_code == 200 and r.json()["deleted"] == 1
    remain = client.get("/api/journal/transactions").json()
    assert len(remain) == 3 and all(t["ticker"] != "삼성전자" for t in remain)
