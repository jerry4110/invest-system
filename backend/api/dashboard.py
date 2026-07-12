"""대시보드 API (F-02) — 지표 조회·수동 갱신."""
from fastapi import APIRouter

from backend.services import market_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/indicators")
def get_indicators():
    """지표별 최신값 + 30일 스파크라인 (FR-02-11~13). 항상 as_of 포함 (NFR-04)."""
    return market_service.get_latest()


@router.post("/refresh")
def refresh():
    """수동 갱신 (FR-02-22). 일부 실패 시에도 200 + failed 목록 (FR-00-08)."""
    return market_service.collect_all()
