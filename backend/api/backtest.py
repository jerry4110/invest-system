"""백테스트 API (M7-1)."""
import tempfile
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import Response

from backend.adapters.broker.file_upload import ParseError
from backend.services import backtest_service as svc

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/upload")
async def upload(file: UploadFile, name: str = Form("업로드 백테스트")):
    suffix = Path(file.filename or "prices.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        return svc.run_buyhold_from_file(tmp_path, name)
    except ParseError as e:
        raise HTTPException(422, str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.get("/runs")
def runs():
    return svc.list_runs()


@router.get("/runs/{run_id}/chart.png")
def chart(run_id: int):
    png = svc.render_chart_png(run_id)
    if png is None:
        raise HTTPException(404, "런을 찾을 수 없습니다")
    return Response(content=png, media_type="image/png")
