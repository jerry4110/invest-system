"""투자전략 API (F-01)."""
from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from backend.adapters.parsers.document import UnsupportedFormat, parse_document
from backend.services import strategy_service as svc
from backend.services.strategy_service import PERSONAS

router = APIRouter(prefix="/api/strategy", tags=["strategy"])


class PersonaBody(BaseModel):
    persona: str


class GuidelineBody(BaseModel):
    text: str


@router.get("")
def get_strategy():
    return svc.get_strategy()


@router.put("/persona")
def put_persona(body: PersonaBody):
    if body.persona not in PERSONAS:
        raise HTTPException(422, f"persona는 {PERSONAS} 중 하나여야 합니다")
    svc.set_persona(body.persona)
    return svc.get_strategy()


@router.put("/guideline")
def put_guideline(body: GuidelineBody):
    version = svc.update_guideline(body.text)
    return {"ok": True, "version": version}


@router.post("/files")
async def upload_file(file: UploadFile):
    try:
        text = parse_document(file.filename or "", await file.read())
    except UnsupportedFormat as e:
        raise HTTPException(422, str(e))
    svc.add_file(file.filename or "지침", text)
    return {"ok": True, "parsed_preview": text[:500]}


@router.put("/allocation")
def put_allocation(alloc: dict[str, float]):
    for k, v in alloc.items():
        if not 0 <= v <= 100:
            raise HTTPException(422, f"{k}: 0~100 사이여야 합니다")
    svc.set_allocation(alloc)
    return {"ok": True}
