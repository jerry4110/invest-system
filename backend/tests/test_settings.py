"""T-02 수용 기준: 설정 조회/변경, 시크릿은 DB에 평문이 존재하지 않음."""
import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "test.db"))
    monkeypatch.setenv("INVEST_MASTER_KEY_FILE", str(tmp_path / "master.key"))
    return TestClient(main_mod.create_app())


def test_get_settings_defaults(client):
    res = client.get("/api/settings")
    assert res.status_code == 200
    body = res.json()
    assert body["refresh_time"] == "08:00"        # FR-10-02 기본값
    assert body["watch_enabled"] is True           # D-013 폴더 감시 기본 on
    assert "watch_folder" in body


def test_update_settings(client):
    res = client.put("/api/settings", json={
        "watch_folder": "C:/Users/Jerry/Downloads",
        "refresh_time": "07:30",
        "watch_enabled": False,
    })
    assert res.status_code == 200
    body = client.get("/api/settings").json()
    assert body["watch_folder"] == "C:/Users/Jerry/Downloads"
    assert body["refresh_time"] == "07:30"
    assert body["watch_enabled"] is False


def test_secret_stored_encrypted(client, tmp_path):
    res = client.put("/api/settings/secrets/openai_api_key",
                     json={"value": "sk-PLAINTEXT-SENTINEL"})
    assert res.status_code == 200
    # 목록은 마스킹된 상태로만 노출, 값은 API로 절대 반환 안 됨
    listed = client.get("/api/settings/secrets").json()
    assert any(s["key"] == "openai_api_key" for s in listed)
    assert all("sk-PLAINTEXT-SENTINEL" not in str(s) for s in listed)
    # DB 파일 어디에도 평문 없음 (constitution §2.5)
    raw = (tmp_path / "test.db").read_bytes()
    assert b"sk-PLAINTEXT-SENTINEL" not in raw


def test_secret_delete(client):
    client.put("/api/settings/secrets/dart_api_key", json={"value": "abc123"})
    res = client.delete("/api/settings/secrets/dart_api_key")
    assert res.status_code == 200
    listed = client.get("/api/settings/secrets").json()
    assert not any(s["key"] == "dart_api_key" for s in listed)
