"""재무 지표 계산 (분석 A, FR-04-02) — 순수 함수, 외부 의존성 없음.

원칙(constitution §2.7): 입력이 없으면 None — 절대 추정하지 않는다.
"""


def _cagr_pct(first: float | None, last: float | None, years: int) -> float | None:
    if not first or last is None or first <= 0 or years <= 0:
        return None
    return round(((last / first) ** (1 / years) - 1) * 100, 2)


def _ratio_pct(num, den) -> float | None:
    if num is None or not den:
        return None
    return round(num / den * 100, 2)


def compute_metrics(financials: list[dict], valuation: dict) -> dict:
    """3개년 손익·재무상태 + 밸류에이션 → 지표 딕셔너리 (값 또는 None)."""
    fin = sorted(financials, key=lambda x: x["year"])
    latest = fin[-1] if fin else {}
    first = fin[0] if fin else {}
    n_years = len(fin) - 1

    rev, ni = latest.get("revenue"), latest.get("net_income")
    equity = latest.get("total_equity")
    liab = latest.get("total_liabilities")

    return {
        # 성장성
        "revenue_growth_pct": _cagr_pct(first.get("revenue"), rev, n_years),
        "net_income_growth_pct": _cagr_pct(first.get("net_income"), ni, n_years),
        # 수익성
        "net_margin_pct": _ratio_pct(ni, rev),
        "operating_margin_pct": _ratio_pct(latest.get("operating_profit"), rev),
        "roe_pct": _ratio_pct(ni, equity),
        # 재무건전성
        "debt_to_equity": round(liab / equity, 4) if liab is not None and equity else None,
        "current_ratio": (round(latest["current_assets"] / latest["current_liabilities"], 4)
                          if latest.get("current_assets") and latest.get("current_liabilities")
                          else None),
        # 밸류에이션 (시장 데이터)
        "per": valuation.get("per"),
        "pbr": valuation.get("pbr"),
        "ev_ebitda": valuation.get("ev_ebitda"),
        "peg": valuation.get("peg"),
        # 현금흐름 (소스 미연동 — 데이터 제공 시 채워짐)
        "fcf_margin_pct": valuation.get("fcf_margin_pct"),
        "fcf_streak": valuation.get("fcf_streak"),
    }
