"""알림 API (M8)."""
from fastapi import APIRouter

from backend.services import alert_service as svc

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(kind: str | None = None):
    return svc.list_alerts(kind=kind)


@router.get("/unread-count")
def unread_count():
    return {"unread": svc.unread_count()}


@router.put("/read-all")
def read_all():
    svc.mark_all_read()
    return {"ok": True}


@router.put("/{alert_id}/read")
def read_one(alert_id: int):
    svc.mark_read(alert_id)
    return {"ok": True}
