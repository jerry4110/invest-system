"""T-30 수용 기준: DB 백업 생성·목록·복원 왕복 (FR-10-05)."""
import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod
from backend.infra.schema import AppSetting


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_path = tmp_path / "invest.db"
    db_mod.init_db(str(db_path))
    from backend.services import backup_service
    monkeypatch.setattr(backup_service, "_db_path", lambda: db_path)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backup")
    return tmp_path


def test_backup_and_restore_roundtrip(env):
    from backend.services import backup_service

    with db_mod.get_session() as s:
        s.merge(AppSetting(key="marker", value="v1"))
        s.commit()
    meta = backup_service.create_backup()
    assert (env / "backup" / meta["filename"]).exists()

    with db_mod.get_session() as s:                       # 백업 후 변경
        s.merge(AppSetting(key="marker", value="v2"))
        s.commit()
    backup_service.restore_backup(meta["filename"])        # 복원
    with db_mod.get_session() as s:
        assert s.get(AppSetting, "marker").value == "v1"   # 백업 시점으로 복귀


def test_backup_api_and_validation(env):
    client = TestClient(main_mod.create_app())
    r = client.post("/api/settings/backup")
    assert r.status_code == 200 and r.json()["filename"].endswith(".db")
    lst = client.get("/api/settings/backups").json()
    assert len(lst) == 1 and lst[0]["filename"] == r.json()["filename"]
    # 경로 탈출·미존재 파일 방어
    assert client.post("/api/settings/restore/..%2Fetc").status_code in (404, 422)
    assert client.post("/api/settings/restore/none.db").status_code == 404
