"""리밸런싱 API (M5)."""
from fastapi import APIRouter, HTTPException

from backend.services import rebalance_service as svc
from backend.services.llm_service import BudgetExceeded

router = APIRouter(prefix="/api/rebalance", tags=["rebalance"])


@router.get("/deviation")
def deviation():
    """목표 대비 이탈도 (FR-05-02) — 프로그램 계산."""
    return svc.get_deviation()


@router.post("/propose")
def propose():
    """리밸런싱 제안 (FR-05-11~15) — LLM + 정합성 재검증."""
    try:
        return svc.propose()
    except BudgetExceeded as e:
        raise HTTPException(429, str(e))
    except (RuntimeError, ValueError) as e:
        raise HTTPException(422, str(e))
