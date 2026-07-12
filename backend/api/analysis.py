"""종목분석 API (M4) — T-22: 재무 조회부터 시작, T-23~26에서 확장."""
from fastapi import APIRouter, HTTPException

from backend.services import analysis_service, financials_service, news_service

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/financials/{ticker}")
def financials(ticker: str):
    """3개년 주요 재무 (FR-04-01). 분석 기준: 최신 확정 사업보고서."""
    try:
        return financials_service.get_financials(ticker)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(422, str(e))


@router.get("/fundamental/{ticker}")
def fundamental(ticker: str):
    """분석 A: 지표 평가·Tier 1 (FR-04-01~04)."""
    try:
        return analysis_service.analyze_fundamental(ticker)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(422, str(e))


@router.get("/compare")
def compare(tickers: str):
    """FR-04-05: 비교 — 쉼표 구분, 대상 포함 2~6개."""
    lst = [t.strip() for t in tickers.split(",") if t.strip()]
    if not 2 <= len(lst) <= 6:
        raise HTTPException(422, "비교는 대상 포함 2~6개 종목이어야 합니다")
    return analysis_service.compare_fundamental(lst)


@router.get("/technical/{ticker}")
def technical(ticker: str):
    """분석 B: 기술적 분석 (FR-04-11~18)."""
    try:
        return analysis_service.analyze_technical(ticker)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(422, str(e))


@router.get("/news/{ticker}")
def news(ticker: str, name: str = ""):
    """분석 C: 뉴스·공시·컨센서스 (FR-04-21~24)."""
    return news_service.analyze_news(ticker, name)
