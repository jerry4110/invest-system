"""APScheduler 배치 등록 (FR-00-21) — 설정된 시각(기본 08:00)에 morning_refresh."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def build_scheduler() -> BackgroundScheduler:
    """설정 기반 스케줄러 구성 (시작은 하지 않음 — 테스트 가능)."""
    from backend.jobs.morning_refresh import run
    from backend.services import settings_service

    hh, mm = settings_service.get_settings()["refresh_time"].split(":")
    sched = BackgroundScheduler(timezone="Asia/Seoul")
    sched.add_job(run, CronTrigger(hour=int(hh), minute=int(mm)),
                  id="morning_refresh", replace_existing=True)
    return sched


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = build_scheduler()
    _scheduler.start()
    logger.info("스케줄러 시작 — morning_refresh @ %s", _scheduler.get_job("morning_refresh").trigger)
