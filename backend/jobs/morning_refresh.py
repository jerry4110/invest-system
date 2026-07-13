"""아침 배치 (FR-00-21·23) — 시장지표 수집 → 잔고 폴더 스캔 → 자산 스냅샷 → JobLog.

실행 경로 3가지:
1. FastAPI 프로세스 내 APScheduler (infra/scheduler.py)
2. Windows 작업 스케줄러: python -m backend.jobs.morning_refresh (README 참조)
3. 앱 시작 시 미실행 보정: run_if_missed()
"""
import logging
import platform
import subprocess
import sys
from datetime import date, datetime

from backend.infra.db import get_session, init_db
from backend.infra.schema import JobLog

logger = logging.getLogger(__name__)
JOB_NAME = "morning_refresh"


def _notify_failure(message: str) -> None:
    """실패 알림 (FR-00-23) — Windows 토스트 (best-effort, 실패해도 무시)."""
    if platform.system() != "Windows":
        return
    try:
        ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
              "ContentType = WindowsRuntime] > $null; "
              "$t = [Windows.UI.Notifications.ToastTemplateType]::ToastText02; "
              "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($t); "
              "$x.GetElementsByTagName('text')[0].AppendChild($x.CreateTextNode('개인투자관리시스템')) > $null; "
              f"$x.GetElementsByTagName('text')[1].AppendChild($x.CreateTextNode('{message}')) > $null; "
              "$n = [Windows.UI.Notifications.ToastNotification]::new($x); "
              "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
              "'invest-system').Show($n)")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=10,
                       capture_output=True)
    except Exception:
        logger.warning("토스트 알림 실패(무시): %s", message)


def run(fetchers=None) -> dict:
    """배치 본체. 개별 단계 실패는 격리하고 JobLog에 기록한다."""
    from backend.services import market_service, portfolio_service, settings_service

    started = datetime.now()
    with get_session() as s:
        log = JobLog(job_name=JOB_NAME, started_at=started, status="running", message="")
        s.add(log)
        s.commit()
        log_id = log.id

    problems: list[str] = []
    scanned = 0
    collect = {"ok": 0, "failed": []}
    try:
        collect = market_service.collect_all(fetchers=fetchers)
        if collect["failed"]:
            problems.append("지표 실패: " + ", ".join(collect["failed"]))
        try:
            folder = settings_service.get_settings()["watch_folder"]
            scanned = portfolio_service.scan_watch_folder(folder)
        except Exception as e:
            problems.append(f"잔고 스캔 오류: {e}")
        try:
            portfolio_service.save_snapshot()
        except Exception as e:
            problems.append(f"스냅샷 오류: {e}")
        try:
            from backend.services import donchian_service
            donchian_service.daily_check()
        except Exception as e:
            problems.append(f"Donchian 점검 오류: {e}")
        status = "partial" if problems else "success"
    except Exception as e:
        status = "failed"
        problems.append(str(e))
        logger.exception("배치 실패")

    finished = datetime.now()
    message = "; ".join(problems) if problems else (
        f"지표 {collect['ok']}종 수집, 잔고 파일 {scanned}건 반영")
    with get_session() as s:
        log = s.get(JobLog, log_id)
        log.status, log.finished_at, log.message = status, finished, message
        s.commit()

    if status != "success":
        _notify_failure(f"아침 배치 {status}: {message[:80]}")
        try:
            from backend.services.alert_service import create_alert
            create_alert("batch_fail", f"아침 배치 {status}", message[:200], toast=False)
        except Exception:
            pass
    logger.info("배치 완료: %s (%s)", status, message)
    return {"status": status, "message": message,
            "duration_sec": (finished - started).total_seconds()}


def run_if_missed(fetchers=None) -> bool:
    """오늘 성공/부분성공 이력이 없으면 즉시 실행 (PC 미가동 대비)."""
    with get_session() as s:
        today_ok = (s.query(JobLog)
                    .filter(JobLog.job_name == JOB_NAME,
                            JobLog.status.in_(("success", "partial")),
                            JobLog.started_at >= datetime.combine(date.today(), datetime.min.time()))
                    .first())
    if today_ok:
        return False
    run(fetchers=fetchers)
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    r = run()
    sys.exit(0 if r["status"] in ("success", "partial") else 1)
