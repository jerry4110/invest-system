"""Donchian API (M7-2)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services import donchian_service as svc

router = APIRouter(prefix="/api/donchian", tags=["donchian"])


class BacktestBody(BaseModel):
    ticker: str = "KOSPI"
    entry_n: int = 20
    exit_n: int = 10
    stop_pct: float = 8.0


@router.post("/backtest")
def backtest(body: BacktestBody):
    if not (2 <= body.entry_n <= 200 and 2 <= body.exit_n <= 200 and 0 < body.stop_pct <= 50):
        raise HTTPException(422, "파라미터 범위: 기간 2~200일, 스탑 0~50%")
    try:
        return svc.backtest(body.ticker, body.entry_n, body.exit_n, body.stop_pct)
    except RuntimeError as e:
        raise HTTPException(422, str(e))


@router.post("/check-now")
def check_now():
    """코스피 시그널 즉시 점검 (FR-07-14 수동 트리거)."""
    try:
        return svc.daily_check()
    except Exception as e:
        raise HTTPException(422, str(e))
