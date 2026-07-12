"""설정·시크릿 서비스 (F-10). 시크릿 값은 암호문으로만 저장·목록은 마스킹."""
from pathlib import Path

from backend.infra.crypto import CryptoBox
from backend.infra.db import get_session
from backend.infra.schema import AppSetting, SecretStore

SETTING_DEFAULTS = {
    "watch_folder": str(Path.home() / "Downloads"),  # D-013 폴더 감시 기본 경로
    "watch_enabled": "true",
    "refresh_time": "08:00",                          # FR-10-02
}


def get_settings() -> dict:
    with get_session() as s:
        rows = {r.key: r.value for r in s.query(AppSetting).all()}
    merged = {**SETTING_DEFAULTS, **rows}
    return {
        "watch_folder": merged["watch_folder"],
        "watch_enabled": merged["watch_enabled"] == "true",
        "refresh_time": merged["refresh_time"],
    }


def update_settings(watch_folder: str | None = None,
                    watch_enabled: bool | None = None,
                    refresh_time: str | None = None) -> dict:
    updates: dict[str, str] = {}
    if watch_folder is not None:
        updates["watch_folder"] = watch_folder
    if watch_enabled is not None:
        updates["watch_enabled"] = "true" if watch_enabled else "false"
    if refresh_time is not None:
        updates["refresh_time"] = refresh_time
    with get_session() as s:
        for k, v in updates.items():
            row = s.get(AppSetting, k) or AppSetting(key=k, value=v)
            row.value = v
            s.merge(row)
        s.commit()
    return get_settings()


def set_secret(key: str, value: str) -> None:
    token = CryptoBox().encrypt(value)
    with get_session() as s:
        s.merge(SecretStore(key=key, encrypted_value=token))
        s.commit()


def get_secret(key: str) -> str | None:
    """내부 전용 — API 응답으로 절대 노출하지 않는다."""
    with get_session() as s:
        row = s.get(SecretStore, key)
    return CryptoBox().decrypt(row.encrypted_value) if row else None


def list_secrets() -> list[dict]:
    with get_session() as s:
        rows = s.query(SecretStore).all()
    return [{"key": r.key, "masked": "••••••••"} for r in rows]


def delete_secret(key: str) -> None:
    with get_session() as s:
        row = s.get(SecretStore, key)
        if row:
            s.delete(row)
            s.commit()
