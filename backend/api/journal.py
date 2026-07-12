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


@router.get("/transactions")
def transactions():
    return svc.list_transactions()


@router.put("/transactions/{tx_id}/note")
def put_note(tx_id: int, body: NoteBody):
    svc.set_note(tx_id, body.note)
    return {"ok": True}


@router.get("/stats")
def stats():
    return svc.get_stats()
