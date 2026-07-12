"""포트폴리오 API (F-03) — 파일 업로드·폴더 스캔·컬럼 매핑 (D-013)."""
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from backend.adapters.broker.file_upload import ParseError
from backend.services import portfolio_service, settings_service

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.post("/upload")
async def upload_balance(file: UploadFile):
    """수동 업로드 (FR-03-04). 파싱 실패 시 422 + 매핑 안내."""
    suffix = Path(file.filename or "잔고.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=f"_잔고{suffix}", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        n = portfolio_service.import_balance_file(tmp_path, account_alias="미래에셋(파일)")
        return {"imported": n}
    except ParseError as e:
        raise HTTPException(422, str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/scan")
def scan_now():
    """감시 폴더 즉시 스캔 (FR-03-01)."""
    folder = settings_service.get_settings()["watch_folder"]
    return {"imported": portfolio_service.scan_watch_folder(folder), "folder": folder}


@router.get("/column-map")
def get_column_map():
    return portfolio_service.get_column_mapping() or {}


@router.put("/column-map")
def put_column_map(mapping: dict[str, str]):
    portfolio_service.set_column_mapping({k: v for k, v in mapping.items() if v.strip()})
    return {"ok": True}


class CashBody(BaseModel):
    amount: float


@router.get("/holdings")
def holdings():
    """보유현황 + 비중·합계·예수금 (FR-03-11~13). as_of 포함 (NFR-04)."""
    return portfolio_service.get_holdings()


@router.put("/cash")
def put_cash(body: CashBody):
    if body.amount < 0:
        raise HTTPException(422, "예수금은 0 이상이어야 합니다")
    portfolio_service.set_cash(body.amount)
    return {"ok": True}


@router.get("/export.csv")
def export_csv():
    """FR-03-14: CSV 내보내기 (엑셀 호환 BOM)."""
    csv_text = portfolio_service.export_csv()
    return Response(content="\ufeff" + csv_text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=portfolio.csv"})
