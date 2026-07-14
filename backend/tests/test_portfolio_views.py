"""포트폴리오 화면 개선 수용 기준 (2026-07-14 시안 확정) — 계좌별·분류별·수동 예수금 우선."""
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod
from backend.infra.schema import MarketIndicator

ACC1 = """유형,종목번호,종목명,구분,보유량,평균단가,현재가,매입금액,평가금액,평가손익,수익률
주식,A005930,삼성전자,현금,100,70000,75000,7000000,7500000,500000,7.14
주식,A455850,SOL AI반도체소부장,현금,100,20000,25000,2000000,2500000,500000,25.0
주식,A442580,PLUS 글로벌HBM반도체,현금,10,50000,100000,500000,1000000,500000,100.0
주식,A0163Y0,ACE 미국우주테크액티브,현금,10,10000,20000,100000,200000,100000,100.0
원화RP,CMARPC01,CMA RP_개인,현금,1000000,1,0,1000000,1000000,0,0
"""
ACC2 = """유형,종목번호,종목명,구분,보유량,평균단가,현재가,매입금액,평가금액,평가손익,수익률
해외주식,NVDA,엔비디아,현금,10,100,150,1000,1500,500,50.0
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    with db_mod.get_session() as s:
        s.add(MarketIndicator(code="USDKRW", name="원/달러", date=date.today(),
                              value=1000.0, change_pct=0, as_of=datetime.now()))
        s.commit()
    c = TestClient(main_mod.create_app())
    for name, text in (("주식계좌.csv", ACC1), ("연금계좌.csv", ACC2)):
        p = tmp_path / name
        p.write_bytes(text.encode("cp949"))
        from backend.services.portfolio_service import import_balance_file
        import_balance_file(p)
    return c


def test_by_account_view(client):
    """계좌별 카드: 종목·예수금·계좌 합계(평가+예수금)·비중."""
    body = client.get("/api/portfolio/by-account").json()
    accounts = {a["name"]: a for a in body["accounts"]}
    a1 = accounts["주식계좌"]
    assert len(a1["holdings"]) == 2
    assert a1["cash"] == 1000000                       # 파일 RP
    assert a1["total"] == 10000000 + 1000000           # 평가 1,000만 + 예수금
    assert a1["pnl_amount"] == 1000000
    a2 = accounts["연금계좌"]
    assert a2["holdings"][0]["eval_amount"] == 1500 * 1000   # USD 환산
    # 비중 합 = 100
    assert round(sum(a["weight_pct"] for a in body["accounts"]), 1) == 100.0
    assert body["as_of"]


def test_manual_cash_overrides_file_on_reimport(client, tmp_path):
    """수동 예수금 우선 정책: 입력 후 파일 재적재해도 수동값 유지."""
    r = client.put("/api/portfolio/cash", json={"amount": 5000000, "account": "주식계좌"})
    assert r.status_code == 200
    accounts = {a["name"]: a for a in client.get("/api/portfolio/by-account").json()["accounts"]}
    assert accounts["주식계좌"]["cash"] == 5000000     # 수동값이 파일 RP(100만) 대체
    assert accounts["주식계좌"]["cash_source"] == "manual"

    p = tmp_path / "주식계좌.csv"                       # 재적재
    p.write_bytes(ACC1.encode("cp949"))
    from backend.services.portfolio_service import import_balance_file
    import_balance_file(p)
    accounts = {a["name"]: a for a in client.get("/api/portfolio/by-account").json()["accounts"]}
    assert accounts["주식계좌"]["cash"] == 5000000     # 여전히 수동값


def test_grouped_invest_4groups(client):
    """투자유형별 4그룹 (2026-07-14 통합): 국내개별 / 해외 / 해외투자 국내ETF / 국내투자 국내ETF."""
    g = client.get("/api/portfolio/grouped?by=invest").json()
    labels = [x["label"] for x in g["groups"]]
    assert labels == ["국내 개별주식", "해외 개별주식·ETF",
                      "해외투자 국내 ETF", "국내투자 국내 ETF"]   # 고정 순서
    by = {x["label"]: x for x in g["groups"]}
    assert by["국내 개별주식"]["eval_amount"] == 7500000            # 삼성전자
    assert by["해외 개별주식·ETF"]["eval_amount"] == 1500000        # NVDA(환산)
    # 글로벌·미국 키워드 → 해외투자 국내 ETF
    assert by["해외투자 국내 ETF"]["eval_amount"] == 1000000 + 200000
    assert by["국내투자 국내 ETF"]["eval_amount"] == 2500000        # SOL AI반도체소부장
    assert all(h.get("account") for x in g["groups"] for h in x["holdings"])

    g3 = client.get("/api/portfolio/grouped?by=sector").json()
    assert "반도체" in {x["label"] for x in g3["groups"]}
    assert client.get("/api/portfolio/grouped?by=type").status_code == 422   # 폐지
    assert client.get("/api/portfolio/grouped?by=bad").status_code == 422
