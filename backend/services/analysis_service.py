"""종목분석 서비스 (M4) — T-23: 분석 A (기초 재무) 조립."""
from datetime import date, datetime, timedelta

from backend.domain.criteria import evaluate
from backend.domain.metrics import compute_metrics


def _load_inputs(ticker: str) -> tuple[list[dict], dict, str]:
    domestic = len(ticker) == 6 and ticker.isalnum() and any(c.isdigit() for c in ticker)
    from backend.adapters.market import yahoo
    if domestic:
        from backend.adapters.market.dart import DartClient
        fin = DartClient().get_major_financials(ticker)
        source = "DART"
    else:
        fin = yahoo.get_financials(ticker)
        balance = yahoo.get_balance(ticker)
        for row in fin:
            row.update(balance.get(row["year"], {}))
        source = "yfinance"
    valuation = yahoo.get_valuation(ticker)
    return fin, valuation, source


def analyze_fundamental(ticker: str) -> dict:
    """분석 A (FR-04-01~04): 3개년 실적 + 지표 평가 + Tier 1. 기준일 T-1."""
    fin, valuation, source = _load_inputs(ticker)
    metrics = compute_metrics(fin, valuation)
    return {
        "ticker": ticker, "source": source,
        "base_date": (date.today() - timedelta(days=1)).isoformat(),  # T-1
        "financials": fin, "valuation": valuation,
        "metrics": metrics, "evaluation": evaluate(metrics),
        "as_of": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": "본 분석은 투자 참고자료이며 최종 판단은 투자자 본인의 책임입니다.",
    }


def compare_fundamental(tickers: list[str]) -> dict:
    """FR-04-05: 비교기업 비교 (대상 포함 3~6개)."""
    results, errors = [], []
    for t in tickers:
        try:
            results.append(analyze_fundamental(t))
        except Exception as e:  # 개별 실패 격리
            errors.append({"ticker": t, "error": str(e)})
    return {"results": results, "errors": errors,
            "as_of": datetime.now().isoformat(timespec="seconds")}
