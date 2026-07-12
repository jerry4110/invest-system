"""리포트 API (M9)."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.services import report_service
from backend.services.llm_service import BudgetExceeded

router = APIRouter(prefix="/api/reports", tags=["reports"])

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.post("/stock/{ticker}")
def generate(ticker: str):
    """종목분석 리포트 생성 (FR-04-41)."""
    try:
        return report_service.generate_stock_report(ticker)
    except BudgetExceeded as e:
        raise HTTPException(429, str(e))


@router.get("")
def list_reports():
    return report_service.list_reports()


@router.get("/{report_id}/download")
def download(report_id: int):
    path = report_service.report_path(report_id)
    if path is None:
        raise HTTPException(404, "리포트를 찾을 수 없습니다")
    return FileResponse(path, media_type=DOCX_MIME, filename=path.name)
