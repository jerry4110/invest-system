"""종목분석 서비스 (M4) — T-23: 분석 A (기초 재무) 조립."""
from datetime import date, datetime, timedelta

from backend.domain.criteria import evaluate
from backend.domain.metrics import compute_metrics
from backend.domain.technical import analyze_technical as _tech_engine


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


def _load_ohlcv(ticker: str, days: int = 180) -> list[dict]:
    from backend.adapters.market import yahoo
    return yahoo.fetch_ohlcv(ticker, days)


def _load_investor_flows(ticker: str) -> list[dict]:
    from backend.adapters.market import krx
    return krx.get_investor_flows(ticker)


def _load_short_interest(ticker: str) -> list[dict]:
    from backend.adapters.market import krx
    return krx.get_short_interest(ticker)


def analyze_technical(ticker: str) -> dict:
    """분석 B (FR-04-11~18): 지표·시그널 + 수급·공매도(국내, 실패 격리)."""
    ohlcv = _load_ohlcv(ticker)
    result = _tech_engine(ohlcv)
    domestic = len(ticker) == 6 and ticker.isalnum() and any(c.isdigit() for c in ticker)

    flows, shorts, notes = None, None, []
    if domestic:
        try:
            flows = _load_investor_flows(ticker)
        except Exception as e:
            notes.append(f"수급 데이터 조회 실패(KRX): {e}")
        try:
            shorts = _load_short_interest(ticker)
        except Exception as e:
            notes.append(f"공매도 데이터 조회 실패(KRX): {e}")
    else:
        notes.append("수급·공매도는 국내 종목만 제공됩니다")

    result.update({
        "ticker": ticker, "ohlcv": ohlcv[-120:],
        "investor_flows": flows, "short_interest": shorts, "notes": notes,
        "base_date": ohlcv[-1]["date"] if ohlcv else None,
        "as_of": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": "본 분석은 투자 참고자료이며 최종 판단은 투자자 본인의 책임입니다.",
    })
    return result


# ── T-26: 종합 판단·AI 토론·딥리서치 (FR-04-31~37, 42~43) ──

def _gather_context(ticker: str) -> dict:
    """분석 A/B/C 요약 텍스트 + 현재가 (LLM 입력용 — 계좌정보 미포함, NFR-01)."""
    parts = []
    price, name = None, ticker
    try:
        fund = analyze_fundamental(ticker)
        ev = fund["evaluation"]
        met = ", ".join(f"{i['label']} {i['value']}({i['status']})"
                        for i in ev["items"] if i["value"] is not None)
        parts.append(f"[A 재무] Tier1 {ev['tier1']['verdict']} | {met}")
    except Exception as e:
        parts.append(f"[A 재무] 조회 실패: {e}")
    try:
        tech = analyze_technical(ticker)
        price = tech["ohlcv"][-1]["close"] if tech.get("ohlcv") else None
        parts.append(f"[B 기술] {tech['signal']['verdict']} (RSI {tech['rsi']}, "
                     f"{tech['ma_alignment']}) — " + "; ".join(tech["signal"]["reasons"][:4]))
    except Exception as e:
        parts.append(f"[B 기술] 조회 실패: {e}")
    try:
        from backend.services.news_service import analyze_news
        news = analyze_news(ticker)
        heads = "; ".join(f"{n['title']}({n.get('sentiment') or '미분류'})"
                          for n in news["news"][:6])
        parts.append(f"[C 뉴스] {heads}")
        if news.get("consensus"):
            parts.append(f"[C 컨센서스] 목표가 {news['consensus']['target_price']}")
    except Exception as e:
        parts.append(f"[C 뉴스] 조회 실패: {e}")
    return {"summary_text": "\n".join(parts), "price": price, "name": name}


def _save_result(ticker: str, kind: str, content: dict) -> None:
    import json as _json
    from backend.infra.db import get_session
    from backend.infra.schema import AnalysisResult
    with get_session() as s:
        s.add(AnalysisResult(ticker=ticker, kind=kind,
                             base_date=(date.today() - timedelta(days=1)).isoformat(),
                             content_json=_json.dumps(content, ensure_ascii=False)))
        s.commit()


_DISCLAIMER = "본 분석은 투자 참고자료이며 최종 판단은 투자자 본인의 책임입니다."


def comprehensive(ticker: str, adapter=None) -> dict:
    """종합 판단 (FR-04-31~34): 적정가·매매 제안·투자 방안."""
    import json as _json
    from backend.services.llm_service import guarded_complete
    from backend.services.strategy_service import get_llm_context

    ctx = _gather_context(ticker)
    result = guarded_complete("comprehensive_judgment", adapter=adapter, max_tokens=1200,
                              ticker=ticker, name=ctx["name"], price=ctx["price"],
                              summary_text=ctx["summary_text"], strategy=get_llm_context())
    text = result.text.strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    out = {"ticker": ticker, "context_summary": ctx["summary_text"], "price": ctx["price"],
           "recommendation": None, "narrative": None,
           "as_of": datetime.now().isoformat(timespec="seconds"), "disclaimer": _DISCLAIMER}
    try:
        parsed = _json.loads(text)
        out.update({k: parsed.get(k) for k in
                    ("fair_value_current", "fair_value_future", "recommendation",
                     "plan", "assumptions", "rationale")})
    except (ValueError, TypeError):
        out["narrative"] = result.text                       # 파싱 실패 — 원문 보존
    _save_result(ticker, "comprehensive", out)
    return out


def debate(ticker: str, adapter=None) -> dict:
    """AI 토론 (FR-04-35): Bull vs Bear → 중재 결론."""
    from backend.services.llm_service import guarded_complete
    from backend.services.strategy_service import get_llm_context

    ctx = _gather_context(ticker)
    strategy = get_llm_context()
    common = dict(ticker=ticker, name=ctx["name"], price=ctx["price"],
                  summary_text=ctx["summary_text"], strategy=strategy)
    bull = guarded_complete("bull_case", adapter=adapter, max_tokens=800, **common).text
    bear = guarded_complete("bear_case", adapter=adapter, max_tokens=800, **common).text
    conclusion = guarded_complete("debate_moderator", adapter=adapter, max_tokens=800,
                                  ticker=ticker, name=ctx["name"],
                                  bull=bull, bear=bear, strategy=strategy).text
    out = {"ticker": ticker, "bull": bull, "bear": bear, "conclusion": conclusion,
           "as_of": datetime.now().isoformat(timespec="seconds"), "disclaimer": _DISCLAIMER}
    _save_result(ticker, "debate", out)
    return out


def deep_research(ticker: str, adapter=None) -> dict:
    """딥리서치 (FR-04-42~43): 4대 행동지침 포함 심층 분석."""
    from backend.services.llm_service import guarded_complete
    from backend.services.strategy_service import get_llm_context

    ctx = _gather_context(ticker)
    result = guarded_complete("deep_research", adapter=adapter, max_tokens=2000,
                              ticker=ticker, name=ctx["name"], price=ctx["price"],
                              summary_text=ctx["summary_text"], strategy=get_llm_context())
    out = {"ticker": ticker, "content": result.text,
           "as_of": datetime.now().isoformat(timespec="seconds"), "disclaimer": _DISCLAIMER}
    _save_result(ticker, "deep", out)
    return out


def get_history(ticker: str) -> list[dict]:
    """FR-04-37: 분석 이력."""
    import json as _json
    from backend.infra.db import get_session
    from backend.infra.schema import AnalysisResult
    with get_session() as s:
        rows = (s.query(AnalysisResult).filter_by(ticker=ticker)
                .order_by(AnalysisResult.id.desc()).limit(20).all())
    return [{"id": r.id, "kind": r.kind, "base_date": r.base_date,
             "created_at": r.created_at.isoformat(timespec="seconds"),
             "content": _json.loads(r.content_json)} for r in rows]
