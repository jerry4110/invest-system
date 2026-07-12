"""T-04 수용 기준: 지표 조회·수동 갱신 API 계약."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod
from backend.services import market_service


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    return TestClient(main_mod.create_app())


def _fake_series(base=100.0):
    today = date.today()
    return [(today - timedelta(days=i), base + i) for i in range(29, -1, -1)]


def test_indicators_empty_before_collect(client):
    res = client.get("/api/dashboard/indicators")
    assert res.status_code == 200
    assert res.json() == []


def test_indicators_after_collect(client):
    from backend.adapters.market.indicators import INDICATORS
    market_service.collect_all(fetchers={c: _fake_series for c in INDICATORS})
    body = client.get("/api/dashboard/indicators").json()
    assert len(body) == 10                       # FR-02-11~12
    item = body[0]
    for field in ("code", "name", "category", "value", "change_pct", "as_of", "spark"):
        assert field in item                     # 계약: as_of 필수 (NFR-04)
    assert len(item["spark"]) == 30              # FR-02-13 스파크라인


def test_manual_refresh_triggers_collect(client, monkeypatch):
    """FR-02-22: 업데이트 버튼 → 수집 트리거."""
    called = {"n": 0}
    def fake_collect(fetchers=None):
        called["n"] += 1
        return {"ok": 10, "failed": [], "as_of": "2026-07-12T08:00:00"}
    monkeypatch.setattr("backend.api.dashboard.market_service", 
                        type("M", (), {"collect_all": staticmethod(fake_collect),
                                       "get_latest": staticmethod(lambda: [])}))
    res = client.post("/api/dashboard/refresh")
    assert res.status_code == 200
    assert called["n"] == 1
    assert res.json()["ok"] == 10


def test_refresh_reports_failures(client, monkeypatch):
    """FR-00-08: 일부 실패 시에도 200 + failed 목록 보고."""
    monkeypatch.setattr("backend.api.dashboard.market_service",
                        type("M", (), {"collect_all": staticmethod(
                            lambda fetchers=None: {"ok": 9, "failed": ["WTI"], "as_of": "x"}),
                            "get_latest": staticmethod(lambda: [])}))
    body = client.post("/api/dashboard/refresh").json()
    assert body["failed"] == ["WTI"]
