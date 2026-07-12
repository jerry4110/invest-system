"""T-10 수용 기준: 아침 배치(JobLog·스냅샷), 부분 실패 기록, 미실행 보정, 이력 API."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod
from backend.infra.schema import JobLog, MarketIndicator


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    return db_mod.get_session


def _fake_series(base=100.0):
    today = date.today()
    return [(today - timedelta(days=i), base + i) for i in range(29, -1, -1)]


def _ok_fetchers():
    from backend.adapters.market.indicators import INDICATORS
    return {c: _fake_series for c in INDICATORS}


def test_morning_refresh_success_logs_and_snapshot(fresh_db):
    """FR-00-21·23: 배치 성공 → 지표 수집 + 스냅샷 + JobLog(success)."""
    from backend.jobs.morning_refresh import run

    result = run(fetchers=_ok_fetchers())
    assert result["status"] == "success"
    with fresh_db() as s:
        log = s.query(JobLog).filter_by(job_name="morning_refresh").one()
        assert log.status == "success"
        assert log.finished_at is not None
        assert s.query(MarketIndicator).count() == 300  # 10지표 × 30일


def test_morning_refresh_partial_failure_recorded(fresh_db):
    """FR-00-08·23: 일부 지표 실패 → partial + 실패 목록 기록, 배치는 계속."""
    from backend.jobs.morning_refresh import run

    fetchers = _ok_fetchers()
    def boom():
        raise ConnectionError("down")
    fetchers["WTI"] = boom
    result = run(fetchers=fetchers)
    assert result["status"] == "partial"
    with fresh_db() as s:
        log = s.query(JobLog).order_by(JobLog.id.desc()).first()
        assert log.status == "partial" and "WTI" in log.message


def test_run_if_missed(fresh_db):
    """PRD_Phase1 §9: 오늘 배치 미실행이면 시작 시 즉시 실행, 이미 성공했으면 skip."""
    from backend.jobs.morning_refresh import run, run_if_missed

    assert run_if_missed(fetchers=_ok_fetchers()) is True    # 첫 실행
    assert run_if_missed(fetchers=_ok_fetchers()) is False   # 오늘 이미 성공 → skip
    with fresh_db() as s:
        assert s.query(JobLog).count() == 1


def test_job_history_api(fresh_db):
    """FR-10-06: 배치 이력 조회."""
    from backend.jobs.morning_refresh import run
    run(fetchers=_ok_fetchers())
    client = TestClient(main_mod.create_app())
    body = client.get("/api/settings/jobs").json()
    assert len(body) >= 1
    assert body[0]["job_name"] == "morning_refresh"
    assert body[0]["status"] == "success" and body[0]["duration_sec"] is not None


def test_scheduler_uses_configured_time(fresh_db, monkeypatch):
    """FR-00-21·FR-10-02: 설정된 시각(예: 07:30)으로 크론 등록."""
    from backend.infra import scheduler as sched_mod
    from backend.services import settings_service
    settings_service.update_settings(refresh_time="07:30")
    s = sched_mod.build_scheduler()
    job = s.get_job("morning_refresh")
    assert job is not None
    trigger = str(job.trigger)
    assert "hour='7'" in trigger and "minute='30'" in trigger
