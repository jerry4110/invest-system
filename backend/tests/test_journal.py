"""T-28 수용 기준: 거래내역 파싱, 이동평균법 실현손익, 중복 방지, 메모, 통계."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod

TRADES_CSV = """거래일자,종목코드,종목명,구분,수량,단가,수수료
2026-06-01,005930,삼성전자,매수,10,100000,50
2026-06-10,005930,삼성전자,매수,10,200000,50
2026-06-20,005930,삼성전자,매도,5,300000,50
2026-06-25,035720,카카오,매수,20,50000,30
2026-07-01,035720,카카오,매도,20,45000,30
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    return TestClient(main_mod.create_app())


def _upload(client, name="거래내역.csv", text=TRADES_CSV):
    return client.post("/api/journal/upload",
                       files={"file": (name, text.encode("utf-8-sig"), "text/csv")})


def test_upload_trades_and_realized_pnl(client):
    """FR-06-01·02: 이동평균법 실현손익.

    삼성전자: 10@10만 + 10@20만 → 평단 15만. 5주 매도@30만
      실현 = (30만-15만)×5 - 수수료50 = 749,950
    카카오: 20@5만 매수, 20주 매도@4.5만 → (4.5만-5만)×20 - 30 = -100,030
    """
    r = _upload(client)
    assert r.status_code == 200 and r.json()["imported"] == 5

    txs = client.get("/api/journal/transactions").json()
    assert len(txs) == 5
    sells = {t["ticker"]: t for t in txs if t["side"] == "sell"}
    assert sells["005930"]["realized_pnl"] == 749950.0
    assert sells["035720"]["realized_pnl"] == -100030.0
    buys = [t for t in txs if t["side"] == "buy"]
    assert all(t["realized_pnl"] is None for t in buys)   # 매수는 실현손익 없음


def test_reupload_no_duplicates(client):
    _upload(client)
    _upload(client)                                        # 같은 파일 재업로드
    assert len(client.get("/api/journal/transactions").json()) == 5


def test_note_update(client):
    """FR-06-03: 판단 근거 기록."""
    _upload(client)
    tx_id = client.get("/api/journal/transactions").json()[0]["id"]
    r = client.put(f"/api/journal/transactions/{tx_id}/note",
                   json={"note": "반도체 업황 회복 기대로 분할매수 1차"})
    assert r.status_code == 200
    txs = client.get("/api/journal/transactions").json()
    assert any(t["note"] == "반도체 업황 회복 기대로 분할매수 1차" for t in txs)


def test_stats_winrate_and_payoff(client):
    """FR-06-05: 승률·손익비·월별 실현손익."""
    _upload(client)
    stats = client.get("/api/journal/stats").json()
    assert stats["sell_count"] == 2
    assert stats["win_rate_pct"] == 50.0                   # 1승 1패
    # 손익비 = 평균이익 749,950 / 평균손실 100,030
    assert round(stats["payoff_ratio"], 2) == 7.5
    monthly = {m["month"]: m["realized_pnl"] for m in stats["monthly"]}
    assert monthly["2026-06"] == 749950.0
    assert monthly["2026-07"] == -100030.0


def test_oversell_isolated(client):
    """보유 수량 초과 매도(데이터 불일치)는 격리 — 해당 행만 경고 처리."""
    bad = """거래일자,종목코드,종목명,구분,수량,단가,수수료
2026-06-01,000660,SK하이닉스,매도,10,200000,50
"""
    r = _upload(client, "거래내역2.csv", bad)
    assert r.status_code == 200
    tx = client.get("/api/journal/transactions").json()
    hy = next(t for t in tx if t["ticker"] == "000660")
    assert hy["realized_pnl"] is None                      # 원가 불명 → 계산 보류
