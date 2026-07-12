"""T-23 수용 기준: 지표 계산(순수 함수)·기준값 평가·Tier 1 판정 — 데이터 없음은 추정 금지."""
import pytest

from backend.domain.metrics import compute_metrics
from backend.domain.criteria import evaluate, DEFAULT_CRITERIA

FIN = [  # 3개년 손익 (억 단위 가정 아님 — 원 단위)
    {"year": 2023, "revenue": 1000, "operating_profit": 150, "net_income": 100,
     "total_assets": 2000, "total_liabilities": 500, "total_equity": 1500,
     "current_assets": 800, "current_liabilities": 400},
    {"year": 2024, "revenue": 1200, "operating_profit": 200, "net_income": 140,
     "total_assets": 2200, "total_liabilities": 550, "total_equity": 1650,
     "current_assets": 900, "current_liabilities": 450},
    {"year": 2025, "revenue": 1440, "operating_profit": 260, "net_income": 190,
     "total_assets": 2500, "total_liabilities": 600, "total_equity": 1900,
     "current_assets": 1000, "current_liabilities": 500},
]
VAL = {"per": 12.0, "pbr": 1.2, "ev_ebitda": 8.0, "peg": 0.9}


def test_compute_metrics_basic():
    m = compute_metrics(FIN, VAL)
    assert m["revenue_growth_pct"] == 20.0        # CAGR: (1440/1000)^(1/2)-1 = 20%
    assert m["net_income_growth_pct"] == pytest.approx(37.84, abs=0.01)
    assert m["net_margin_pct"] == pytest.approx(13.19, abs=0.01)   # 190/1440
    assert m["operating_margin_pct"] == pytest.approx(18.06, abs=0.01)
    assert m["roe_pct"] == pytest.approx(10.0, abs=0.01)           # 190/1900
    assert m["debt_to_equity"] == pytest.approx(0.32, abs=0.01)    # 600/1900
    assert m["current_ratio"] == pytest.approx(2.0)                # 1000/500
    assert m["per"] == 12.0 and m["peg"] == 0.9


def test_missing_data_is_none_not_estimated():
    """constitution §2.7: 데이터 없으면 추정하지 말고 없음 표기."""
    fin = [{"year": 2025, "revenue": 100, "net_income": 10}]       # 1개년·BS 없음
    m = compute_metrics(fin, {})
    assert m["revenue_growth_pct"] is None
    assert m["roe_pct"] is None and m["per"] is None
    assert m["net_margin_pct"] == 10.0                              # 계산 가능한 것만


def test_evaluate_statuses():
    m = compute_metrics(FIN, VAL)
    ev = evaluate(m)
    by = {e["metric"]: e for e in ev["items"]}
    # 매출성장 20% ≥ 기준 15% → 충족
    assert by["revenue_growth_pct"]["status"] == "충족"
    # ROE 10% < 최소 15% → 미충족
    assert by["roe_pct"]["status"] == "미충족"
    # PEG 0.9 ≤ 1.5 → 충족
    assert by["peg"]["status"] == "충족"
    # 데이터 없는 지표는 '데이터 없음'
    m2 = compute_metrics([{"year": 2025, "revenue": 100}], {})
    ev2 = evaluate(m2)
    assert any(e["status"] == "데이터 없음" for e in ev2["items"])


def test_tier1_verdict():
    """Tier 1: 성장 20%+, ROE 25%+, 순이익률 15%+, PEG 1.0-, 부채비율 0.3- 동시 충족."""
    strong = compute_metrics([
        {"year": 2023, "revenue": 1000, "operating_profit": 300, "net_income": 200,
         "total_assets": 1500, "total_liabilities": 200, "total_equity": 1300,
         "current_assets": 800, "current_liabilities": 300},
        {"year": 2024, "revenue": 1300, "operating_profit": 400, "net_income": 280,
         "total_assets": 1700, "total_liabilities": 220, "total_equity": 1480,
         "current_assets": 900, "current_liabilities": 320},
        {"year": 2025, "revenue": 1690, "operating_profit": 550, "net_income": 400,
         "total_assets": 1800, "total_liabilities": 250, "total_equity": 1550,  # ROE 25.8%
         "current_assets": 1000, "current_liabilities": 350},
    ], {"peg": 0.8, "per": 15, "pbr": 3, "ev_ebitda": 10})
    v = evaluate(strong)["tier1"]
    assert v["verdict"] == "충족"                                   # 판정 가능 조건 전부 통과
    assert "fcf_streak" in v["unknown"]                             # FCF 미제공 → 판정불가 명시

    weak = evaluate(compute_metrics(FIN, VAL))["tier1"]
    assert weak["verdict"] == "미충족"
    assert "roe_pct" in weak["failed"]


def test_criteria_override(tmp_path, monkeypatch):
    """FR-04-06: 기준값 커스터마이징."""
    from backend.infra import db as db_mod
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    from backend.domain.criteria import get_criteria, set_criteria_overrides

    assert get_criteria()["roe_pct"]["min"] == DEFAULT_CRITERIA["roe_pct"]["min"]
    set_criteria_overrides({"roe_pct": {"min": 8.0}})
    assert get_criteria()["roe_pct"]["min"] == 8.0
    ev = evaluate(compute_metrics(FIN, VAL))                        # ROE 10% ≥ 8 → 충족
    assert {e["metric"]: e for e in ev["items"]}["roe_pct"]["status"] == "충족"


def test_analysis_api_contract(tmp_path, monkeypatch):
    """T-23 API: 분석 A 응답 계약 + 비교 검증 + 고지문 (FR-04-36)."""
    from fastapi.testclient import TestClient
    from backend import main as main_mod
    from backend.infra import db as db_mod
    from backend.services import analysis_service

    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    monkeypatch.setattr(analysis_service, "_load_inputs",
                        lambda t: (FIN, VAL, "TEST"))
    client = TestClient(main_mod.create_app())

    body = client.get("/api/analysis/fundamental/005930").json()
    assert body["evaluation"]["tier1"]["verdict"] in ("충족", "미충족", "판정 불가")
    assert body["base_date"] and body["as_of"]                    # T-1·NFR-04
    assert "참고자료" in body["disclaimer"]                        # FR-04-36

    cmp = client.get("/api/analysis/compare?tickers=005930,000660").json()
    assert len(cmp["results"]) == 2
    assert client.get("/api/analysis/compare?tickers=005930").status_code == 422
