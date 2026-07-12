"""설정 API (F-10)."""
from fastapi import APIRouter
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
