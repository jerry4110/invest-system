"""13F API (M7-3)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services import f13_service as svc

router = APIRouter(prefix="/api/13f", tags=["13f"])


class InstBody(BaseModel):
    name: str
    cik: str


@router.get("/institutions")
def institutions():
    return svc.list_institutions()


@router.post("/institutions")
def add_institution(body: InstBody):
    try:
        svc.add_institution(body.name, body.cik)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}


@router.get("/{cik}")
def portfolio(cik: str):
    try:
        return svc.get_portfolio(cik)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(422, str(e))
