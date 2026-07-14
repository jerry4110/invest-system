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
def scan_now(force: bool = False):
    """감시 폴더 즉시 스캔 (FR-03-01). force=true면 처리 이력 무시 재처리."""
    folder = settings_service.get_settings()["watch_folder"]
    detail = portfolio_service.scan_watch_folder_detail(folder, force=force)
    detail["folder"] = folder
    return detail


@router.get("/column-map")
def get_column_map():
    return portfolio_service.get_column_mapping() or {}


@router.put("/column-map")
def put_column_map(mapping: dict[str, str]):
    portfolio_service.set_column_mapping({k: v for k, v in mapping.items() if v.strip()})
    return {"ok": True}


class CashBody(BaseModel):
    amount: float
    account: str | None = None


@router.get("/holdings")
def holdings():
    """보유현황 + 비중·합계·예수금 (FR-03-11~13). as_of 포함 (NFR-04)."""
    return portfolio_service.get_holdings()


@router.put("/cash")
def put_cash(body: CashBody):
    if body.amount < 0:
        raise HTTPException(422, "예수금은 0 이상이어야 합니다")
    if body.account:
        portfolio_service.set_cash(body.amount, account_alias=body.account)
    else:
        portfolio_service.set_cash(body.amount)
    return {"ok": True}


@router.get("/export.csv")
def export_csv():
    """FR-03-14: CSV 내보내기 (엑셀 호환 BOM)."""
    csv_text = portfolio_service.export_csv()
    return Response(content="\ufeff" + csv_text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=portfolio.csv"})


@router.get("/analysis")
def analysis():
    """유형·산업별 구성 (FR-03-21~23)."""
    return portfolio_service.get_analysis()


@router.get("/returns")
def returns():
    """기간 수익률·벤치마크 (FR-03-24~25)."""
    return portfolio_service.get_period_returns()


@router.get("/trend")
def trend():
    """자산 추이 (FR-03-26)."""
    return portfolio_service.get_trend()


@router.post("/reset")
def reset_all():
    """포트폴리오 전체 초기화 (D-020) — 이후 폴더 스캔으로 재적재."""
    portfolio_service.reset_all()
    return {"ok": True}


@router.get("/by-account")
def by_account():
    """계좌별 카드 뷰 (2026-07-14 화면 개선)."""
    return portfolio_service.get_by_account()


@router.get("/grouped")
def grouped(by: str):
    """분류별 뷰: type(주식·ETF) | region(국내·해외) | sector(산업)."""
    try:
        return portfolio_service.get_grouped(by)
    except ValueError as e:
        raise HTTPException(422, str(e))
