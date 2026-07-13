"""T-31 수용 기준: 알림 생성·목록·읽음 처리·미읽음 수·종류 필터 (FR-08-01~06)."""
import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    return TestClient(main_mod.create_app())


def _seed():
    from backend.services import alert_service
    alert_service.create_alert("donchian", "코스피 Donchian 매수 시그널",
                               "20일 채널 상단 돌파 (7,480)", toast=False)
    alert_service.create_alert("price_move", "삼성전자 +5.2% 급등",
                               "285,000 → 299,800", toast=False)
    return alert_service


def test_create_list_and_unread(client):
    _seed()
    body = client.get("/api/alerts").json()
    assert len(body["alerts"]) == 2
    assert body["unread"] == 2
    a = body["alerts"][0]
    assert a["kind"] and a["title"] and a["created_at"] and a["read"] is False


def test_mark_read_and_read_all(client):
    _seed()
    first_id = client.get("/api/alerts").json()["alerts"][0]["id"]
    assert client.put(f"/api/alerts/{first_id}/read").status_code == 200
    assert client.get("/api/alerts").json()["unread"] == 1
    client.put("/api/alerts/read-all")
    assert client.get("/api/alerts").json()["unread"] == 0


def test_kind_filter_and_dedup_same_day(client):
    """같은 날 동일 kind+title 중복 생성 방지 (배치 재실행 대비)."""
    svc = _seed()
    svc.create_alert("donchian", "코스피 Donchian 매수 시그널", "중복", toast=False)
    body = client.get("/api/alerts?kind=donchian").json()
    assert len(body["alerts"]) == 1                        # 중복 안 쌓임
    assert body["alerts"][0]["kind"] == "donchian"


def test_unread_badge_endpoint(client):
    _seed()
    assert client.get("/api/alerts/unread-count").json()["unread"] == 2
