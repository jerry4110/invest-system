"""리밸런싱 서비스 (M5, FR-05-01~17) — 이탈도(프로그램) + LLM 제안(정합성 재검증)."""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
_DISCLAIMER = "본 제안은 투자 참고자료이며 최종 판단과 주문 실행은 투자자 본인의 책임입니다."


def _default_adapter():
    return None  # guarded_complete가 OpenAI 기본 사용


def get_deviation() -> dict:
    """FR-05-02: 현재 배분 vs 목표(target_allocation) 이탈도 — 프로그램 계산."""
    from backend.services.portfolio_service import get_holdings
    from backend.services.strategy_service import get_strategy

    d = get_holdings()
    t = d["totals"]
    total = t["total_asset"] or 1
    stock_eval = t["eval_amount"]
    domestic = sum(h["eval_amount"] for h in d["holdings"] if h["market"] == "KRX")

    current = {
        "stock_pct": round(stock_eval / total * 100, 2),
        "cash_pct": round(t["cash"] / total * 100, 2),
        "domestic_pct": round(domestic / stock_eval * 100, 2) if stock_eval else 0.0,
        "overseas_pct": round((stock_eval - domestic) / stock_eval * 100, 2) if stock_eval else 0.0,
    }
    labels = {"stock_pct": "주식 비중", "cash_pct": "현금 비중",
              "domestic_pct": "국내 비중(주식 내)", "overseas_pct": "해외 비중(주식 내)"}
    target = get_strategy()["allocation"]
    deviations = [{
        "key": k, "label": labels.get(k, k),
        "current_pct": current.get(k), "target_pct": v,
        "deviation_pp": round(current.get(k, 0) - v, 2),
    } for k, v in target.items() if k in current]
    return {"deviations": deviations, "totals": t,
            "as_of": d["as_of"] or datetime.now().isoformat(timespec="seconds")}


def _validate(actions: list[dict], holdings_by_ticker: dict) -> list[str]:
    """LLM 제안 정합성 — 프로그램 재검증 (constitution §2.7)."""
    warnings = []
    for a in actions:
        if not (a.get("rationale") or "").strip():
            warnings.append(f"{a.get('name', a.get('ticker'))}: 근거(rationale) 누락")
        h = holdings_by_ticker.get(a.get("ticker"))
        if a.get("action") in ("매도", "편출"):
            if h is None:
                warnings.append(f"{a.get('ticker')}: 보유하지 않은 종목의 매도 제안")
            elif a.get("qty", 0) > h["qty"]:
                warnings.append(f"{a.get('name')}: 보유 수량({h['qty']:,.0f}) 초과 매도 제안({a['qty']:,})")
        if h and a.get("qty") and a.get("est_amount"):
            calc = a["qty"] * h["cur_price"]
            if calc and abs(calc - a["est_amount"]) / calc > 0.05:
                warnings.append(f"{a.get('name')}: 예상금액 불일치 (계산 {calc:,.0f} vs 제안 {a['est_amount']:,.0f})")
    return warnings


def _before_after(actions: list[dict], totals: dict) -> list[dict]:
    """FR-05-15: 제안 적용 시 주식/현금 비중 변화 (프로그램 계산)."""
    total = totals["total_asset"] or 1
    delta_cash = 0.0
    for a in actions:
        amt = a.get("est_amount") or 0
        if a.get("action") in ("매도", "편출"):
            delta_cash += amt
        elif a.get("action") in ("매수", "신규편입"):
            delta_cash -= amt
    stock_after = totals["eval_amount"] - delta_cash
    cash_after = totals["cash"] + delta_cash
    rows = [
        ("stock_pct", "주식 비중", totals["eval_amount"] / total * 100, stock_after / total * 100),
        ("cash_pct", "현금 비중", totals["cash"] / total * 100, cash_after / total * 100),
    ]
    return [{"key": k, "label": lbl, "before_pct": round(b, 2), "after_pct": round(af, 2)}
            for k, lbl, b, af in rows]


def propose(adapter=None) -> dict:
    """FR-05-11~15: LLM 리밸런싱 제안 + 정합성 재검증 + 전후 비교 + 이력 저장."""
    from backend.services.analysis_service import _save_result
    from backend.services.llm_service import guarded_complete
    from backend.services.portfolio_service import get_holdings
    from backend.services.strategy_service import get_llm_context

    dev = get_deviation()
    port = get_holdings()
    holdings_txt = "\n".join(
        f"- {h['name']}({h['ticker']}): {h['qty']:,.0f}주 × {h['cur_price']:,.0f} = "
        f"{h['eval_amount']:,.0f}원 ({h['weight_pct']}%, 수익률 {h['pnl_pct']:+.1f}%, 섹터 {h.get('sector') or '-'})"
        for h in port["holdings"])
    dev_txt = "\n".join(f"- {d['label']}: 현재 {d['current_pct']}% / 목표 {d['target_pct']}% "
                        f"(이탈 {d['deviation_pp']:+.1f}%p)" for d in dev["deviations"])

    result = guarded_complete("rebalance_proposal", adapter=adapter or _default_adapter(),
                              max_tokens=1500,
                              total_asset=f"{dev['totals']['total_asset']:,.0f}",
                              total_eval=f"{dev['totals']['eval_amount']:,.0f}",
                              total_cash=f"{dev['totals']['cash']:,.0f}",
                              deviations=dev_txt, holdings=holdings_txt,
                              strategy=get_llm_context())
    text = result.text.strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()

    out = {"deviations": dev["deviations"], "actions": [], "summary": None,
           "warnings": [], "narrative": None,
           "as_of": datetime.now().isoformat(timespec="seconds"),
           "disclaimer": _DISCLAIMER}
    try:
        parsed = json.loads(text)
        out["actions"] = parsed.get("actions", [])
        out["summary"] = parsed.get("summary")
        out["target_cash_pct"] = parsed.get("target_cash_pct")
    except (ValueError, TypeError):
        out["narrative"] = result.text
        out["warnings"].append("AI 응답 파싱 실패 — 원문을 확인하세요")

    by_ticker = {h["ticker"]: h for h in port["holdings"]}
    out["warnings"].extend(_validate(out["actions"], by_ticker))
    out["before_after"] = _before_after(out["actions"], dev["totals"])
    _save_result("PORTFOLIO", "rebalance", out)
    return out
