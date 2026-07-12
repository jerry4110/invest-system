"""평가 기준값 (기능요건정의서 §M4 분석 A 기준표) + 충족 판정·Tier 1.

기본값은 정의서 그대로, 사용자 오버라이드는 app_setting(analysis_criteria) — FR-04-06.
direction: min(이상 충족) | max(이하 충족)
"""
import json

DEFAULT_CRITERIA: dict[str, dict] = {
    "revenue_growth_pct":    {"label": "매출 성장률(3y)", "direction": "min", "min": 15.0, "floor": 10.0},
    "net_income_growth_pct": {"label": "순이익 성장률(3y·EPS 대용)", "direction": "min", "min": 15.0},
    "net_margin_pct":        {"label": "순이익률", "direction": "min", "min": 10.0},
    "operating_margin_pct":  {"label": "영업이익률", "direction": "min", "min": 15.0},
    "roe_pct":               {"label": "ROE", "direction": "min", "min": 15.0},
    "fcf_margin_pct":        {"label": "FCF 마진", "direction": "min", "min": 8.0},
    "peg":                   {"label": "PEG", "direction": "max", "max": 1.5},
    "per":                   {"label": "PER(Forward 대용)", "direction": "max", "max": 25.0},
    "ev_ebitda":             {"label": "EV/EBITDA", "direction": "max", "max": 15.0},
    "pbr":                   {"label": "PBR(성장주 기준)", "direction": "max", "max": 5.0},
    "debt_to_equity":        {"label": "부채비율(D/E)", "direction": "max", "max": 0.5},
    "current_ratio":         {"label": "유동비율", "direction": "min", "min": 1.5},
}

# Tier 1 동시 충족 조건 (정의서) — fcf_streak(3년 연속 FCF 증가)·질적 요소는 별도
TIER1 = {
    "revenue_growth_pct": ("min", 20.0),
    "net_income_growth_pct": ("min", 20.0),
    "roe_pct": ("min", 25.0),
    "net_margin_pct": ("min", 15.0),
    "peg": ("max", 1.0),
    "debt_to_equity": ("max", 0.3),
    "fcf_streak": ("min", 3.0),
}


def get_criteria() -> dict:
    from backend.infra.db import get_session
    from backend.infra.schema import AppSetting

    merged = {k: dict(v) for k, v in DEFAULT_CRITERIA.items()}
    with get_session() as s:
        row = s.get(AppSetting, "analysis_criteria")
    if row and row.value:
        for k, override in json.loads(row.value).items():
            if k in merged:
                merged[k].update(override)
    return merged


def set_criteria_overrides(overrides: dict) -> None:
    from backend.infra.db import get_session
    from backend.infra.schema import AppSetting
    with get_session() as s:
        s.merge(AppSetting(key="analysis_criteria",
                           value=json.dumps(overrides, ensure_ascii=False)))
        s.commit()


def _status(value, spec) -> str:
    if value is None:
        return "데이터 없음"
    if spec["direction"] == "min":
        if value >= spec["min"]:
            return "충족"
        if "floor" in spec and value >= spec["floor"]:
            return "부분충족"
        return "미충족"
    return "충족" if value <= spec["max"] else "미충족"


def evaluate(metrics: dict) -> dict:
    """지표별 충족 판정 + Tier 1 종합 (판정 불가 조건은 unknown으로 명시)."""
    criteria = get_criteria()
    items = [{
        "metric": key, "label": spec["label"], "value": metrics.get(key),
        "threshold": spec.get("min", spec.get("max")),
        "direction": spec["direction"],
        "status": _status(metrics.get(key), spec),
    } for key, spec in criteria.items()]

    passed, failed, unknown = [], [], []
    for key, (direction, threshold) in TIER1.items():
        v = metrics.get(key)
        if v is None:
            unknown.append(key)
        elif (direction == "min" and v >= threshold) or (direction == "max" and v <= threshold):
            passed.append(key)
        else:
            failed.append(key)
    verdict = "미충족" if failed else ("충족" if passed else "판정 불가")
    return {"items": items,
            "tier1": {"verdict": verdict, "passed": passed, "failed": failed,
                      "unknown": unknown}}
