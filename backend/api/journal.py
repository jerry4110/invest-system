"""투자저널 API (M6)."""
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from backend.adapters.broker.file_upload import ParseError
from backend.services import journal_service as svc

router = APIRouter(prefix="/api/journal", tags=["journal"])


class NoteBody(BaseModel):
    note: str


@router.post("/upload")
async def upload_trades(file: UploadFile):
    suffix = Path(file.filename or "거래내역.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        return {"imported": svc.import_trades_file(tmp_path)}
    except ParseError as e:
        raise HTTPException(422, str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


class DeleteBody(BaseModel):
    ids: list[int]


@router.get("/transactions")
def transactions(date_from: str | None = None, date_to: str | None = None):
    return svc.list_transactions(date_from, date_to)


@router.delete("/transactions")
def delete_transactions(body: DeleteBody):
    """체크 선택 삭제."""
    return {"deleted": svc.delete_transactions(body.ids)}


@router.put("/transactions/{tx_id}/note")
def put_note(tx_id: int, body: NoteBody):
    svc.set_note(tx_id, body.note)
    return {"ok": True}


@router.get("/stats")
def stats(date_from: str | None = None, date_to: str | None = None):
    return svc.get_stats(date_from, date_to)
