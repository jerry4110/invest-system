"""종목분석 API (M4) — T-22: 재무 조회부터 시작, T-23~26에서 확장."""
from fastapi import APIRouter, HTTPException

from backend.services import financials_service

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/financials/{ticker}")
def financials(ticker: str):
    """3개년 주요 재무 (FR-04-01). 분석 기준: 최신 확정 사업보고서."""
    try:
        return financials_service.get_financials(ticker)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(422, str(e))
