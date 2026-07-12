"""다운로드 폴더 감시 (D-013) — 데몬 스레드 폴링 (15초 간격)."""
import logging
import threading
import time

logger = logging.getLogger(__name__)
_started = False


def start_watcher(interval: int = 15) -> None:
    global _started
    if _started:
        return
    _started = True

    def loop():
        from backend.services import portfolio_service, settings_service
        while True:
            try:
                cfg = settings_service.get_settings()
                if cfg["watch_enabled"]:
                    n = portfolio_service.scan_watch_folder(cfg["watch_folder"])
                    if n:
                        logger.info("폴더 감시: 잔고 파일 %d건 자동 임포트", n)
            except Exception as e:  # 감시 실패가 앱을 죽이지 않도록 격리
                logger.warning("폴더 감시 오류(무시): %s", e)
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True, name="balance-watcher").start()
