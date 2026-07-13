"""알림 서비스 (M8, FR-08-01~06) — 앱 내 이력 + Windows 토스트 (D-017)."""
import logging
from datetime import date, datetime

from backend.infra.db import get_session
from backend.infra.schema import Alert

logger = logging.getLogger(__name__)


def create_alert(kind: str, title: str, body: str = "", toast: bool = True) -> int | None:
    """알림 생성. 같은 날 동일 kind+title은 중복 생성하지 않는다 (배치 재실행 대비)."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    with get_session() as s:
        dup = (s.query(Alert).filter(Alert.kind == kind, Alert.title == title,
                                     Alert.created_at >= today_start).first())
        if dup:
            return None
        a = Alert(kind=kind, title=title, body=body)
        s.add(a)
        s.commit()
        alert_id = a.id
    logger.info("알림 생성 [%s] %s", kind, title)
    if toast:
        from backend.jobs.morning_refresh import _notify_failure as _toast
        _toast(f"{title} — {body[:60]}")
    return alert_id


def list_alerts(kind: str | None = None, limit: int = 50) -> dict:
    with get_session() as s:
        q = s.query(Alert)
        if kind:
            q = q.filter_by(kind=kind)
        rows = q.order_by(Alert.id.desc()).limit(limit).all()
        unread = s.query(Alert).filter_by(read=False).count()
    return {"alerts": [{
        "id": a.id, "kind": a.kind, "title": a.title, "body": a.body,
        "read": a.read, "created_at": a.created_at.isoformat(timespec="seconds"),
    } for a in rows], "unread": unread}


def mark_read(alert_id: int) -> None:
    with get_session() as s:
        a = s.get(Alert, alert_id)
        if a:
            a.read = True
            s.commit()


def mark_all_read() -> None:
    with get_session() as s:
        s.query(Alert).filter_by(read=False).update({"read": True})
        s.commit()


def unread_count() -> int:
    with get_session() as s:
        return s.query(Alert).filter_by(read=False).count()
