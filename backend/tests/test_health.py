"""T-01 수용 기준: 헬스체크 API가 상태와 버전을 반환한다."""
from fastapi.testclient import TestClient

from backend.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app())
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "as_of" in body  # NFR-04: 모든 응답에 기준시각
