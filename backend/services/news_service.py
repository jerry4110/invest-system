"""분석 C 서비스 (FR-04-21~24) — 공시·뉴스·컨센서스 + LLM 분류 (실패 격리)."""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _load_disclosures(ticker: str) -> list[dict]:
    from backend.adapters.market.dart import DartClient
    return DartClient().get_disclosures(ticker, days=30)


def _load_news(ticker: str, name: str) -> list[dict]:
    from backend.adapters.market import news as news_adapter
    domestic = len(ticker) == 6 and any(c.isdigit() for c in ticker)
    if domestic:
        return news_adapter.fetch_google_news(f'"{name or ticker}" 주가')
    return news_adapter.fetch_yf_news(ticker)


def _load_consensus(ticker: str) -> dict | None:
    """애널리스트 컨센서스 (FR-04-22 대용 — yfinance 목표가·추천)."""
    import yfinance as yf
    from backend.adapters.market.yahoo import _yf_symbol
    info = yf.Ticker(_yf_symbol(ticker)).info or {}
    if not info.get("targetMeanPrice"):
        return None
    return {"target_price": info.get("targetMeanPrice"),
            "analysts": info.get("numberOfAnalystOpinions"),
            "recommendation": info.get("recommendationKey")}


def classify_news(items: list[dict], adapter=None) -> tuple[list[dict], list[str]]:
    """LLM 호재/악재 분류 (FR-04-23). 실패·예산 초과 시 미분류 반환 + 사유."""
    from backend.services.llm_service import BudgetExceeded, guarded_complete

    if not items:
        return items, []
    notes: list[str] = []
    news_list = "\n".join(f"{i}. {it['title']}" for i, it in enumerate(items[:10]))
    try:
        result = guarded_complete("news_classify", adapter=adapter, max_tokens=800,
                                  name=items[0].get("name", ""), news_list=news_list)
        text = result.text.strip()
        if text.startswith("```"):
            text = text.strip("`").lstrip("json").strip()
        for row in json.loads(text):
            idx = row.get("index")
            if isinstance(idx, int) and 0 <= idx < len(items):
                items[idx].update({"sentiment": row.get("sentiment"),
                                   "importance": row.get("importance"),
                                   "summary": row.get("summary")})
    except BudgetExceeded as e:
        notes.append(str(e))
    except Exception as e:
        logger.warning("뉴스 LLM 분류 실패(격리): %s", e)
        notes.append("AI 분류 실패 — 뉴스는 미분류로 표시됩니다")
    return items, notes


def analyze_news(ticker: str, name: str = "") -> dict:
    """분석 C 조립 — 각 소스 실패는 격리."""
    disclosures, news, consensus, notes = [], [], None, []
    domestic = len(ticker) == 6 and any(c.isdigit() for c in ticker)

    if domestic:
        try:
            disclosures = _load_disclosures(ticker)
        except Exception as e:
            notes.append(f"공시 조회 실패: {e}")
    try:
        news = _load_news(ticker, name)
    except Exception as e:
        notes.append(f"뉴스 조회 실패: {e}")
    try:
        consensus = _load_consensus(ticker)
    except Exception as e:
        notes.append(f"컨센서스 조회 실패: {e}")

    news, llm_notes = classify_news(news)
    notes.extend(llm_notes)

    return {"ticker": ticker, "disclosures": disclosures, "news": news,
            "consensus": consensus, "notes": notes,
            "as_of": datetime.now().isoformat(timespec="seconds"),
            "disclaimer": "본 분석은 투자 참고자료이며 최종 판단은 투자자 본인의 책임입니다. 모든 항목의 출처 링크를 확인하세요."}
