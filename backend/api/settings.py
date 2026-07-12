"""설정 API (F-10)."""
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services import settings_service as svc

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    watch_folder: str | None = None
    watch_enabled: bool | None = None
    refresh_time: str | None = None


class SecretValue(BaseModel):
    value: str


@router.get("")
def get_settings():
    return svc.get_settings()


@router.put("")
def put_settings(body: SettingsUpdate):
    if body.refresh_time is not None and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", body.refresh_time):
        raise HTTPException(422, "refresh_time은 HH:MM 형식이어야 합니다")  # Codex 리뷰 반영
    if body.watch_folder is not None and not body.watch_folder.strip():
        raise HTTPException(422, "watch_folder는 비워둘 수 없습니다")
    return svc.update_settings(body.watch_folder, body.watch_enabled, body.refresh_time)


@router.get("/secrets")
def list_secrets():
    return svc.list_secrets()  # 값은 절대 반환하지 않음 (NFR-01)


@router.put("/secrets/{key}")
def put_secret(key: str, body: SecretValue):
    svc.set_secret(key, body.value)
    return {"ok": True, "key": key}


@router.delete("/secrets/{key}")
def delete_secret(key: str):
    svc.delete_secret(key)
    return {"ok": True}


@router.get("/jobs")
def job_history():
    """배치 실행 이력 (FR-10-06·FR-00-23)."""
    from backend.infra.db import get_session
    from backend.infra.schema import JobLog

    with get_session() as s:
        rows = s.query(JobLog).order_by(JobLog.id.desc()).limit(30).all()
    return [{
        "job_name": r.job_name, "status": r.status,
        "started_at": r.started_at.isoformat(timespec="seconds"),
        "duration_sec": round((r.finished_at - r.started_at).total_seconds(), 1)
                        if r.finished_at else None,
        "message": r.message,
    } for r in rows]


class LlmLimitBody(BaseModel):
    limit_usd: float


@router.get("/llm-usage")
def llm_usage():
    """LLM 월 사용량·상한 (D-015)."""
    from backend.services import llm_service
    return llm_service.get_usage_summary()


@router.put("/llm-limit")
def put_llm_limit(body: LlmLimitBody):
    if body.limit_usd < 0:
        raise HTTPException(422, "상한은 0 이상이어야 합니다")
    from backend.services import llm_service
    llm_service.set_monthly_limit(body.limit_usd)
    return {"ok": True, "limit_usd": body.limit_usd}
