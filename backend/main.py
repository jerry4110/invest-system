"""FastAPI 엔트리 — 실행: uvicorn backend.main:app --port 8000"""
from datetime import datetime

from fastapi import FastAPI

from backend.api.analysis import router as analysis_router
from backend.api.dashboard import router as dashboard_router
from backend.api.journal import router as journal_router
from backend.api.portfolio import router as portfolio_router
from backend.api.reports import router as reports_router
from backend.api.settings import router as settings_router
from backend.api.strategy import router as strategy_router

APP_VERSION = "0.9.0"  # Phase 2 / T-27


def create_app() -> FastAPI:
    app = FastAPI(title="개인투자관리시스템 API", version=APP_VERSION)
    app.include_router(settings_router)
    app.include_router(dashboard_router)
    app.include_router(portfolio_router)
    app.include_router(strategy_router)
    app.include_router(journal_router)
    app.include_router(analysis_router)
    app.include_router(reports_router)

    @app.on_event("startup")
    def _start_background():
        import threading

        from backend.infra.db import init_db
        from backend.infra.scheduler import start_scheduler
        from backend.infra.watcher import start_watcher
        init_db()
        start_watcher()      # D-013 폴더 감시
        start_scheduler()    # FR-00-21 08:00 배치

        def _catch_up():
            from backend.jobs.morning_refresh import run_if_missed
            try:
                if run_if_missed():
                    pass  # 오늘 미실행분 보정 실행됨
            except Exception:
                pass
        threading.Thread(target=_catch_up, daemon=True).start()

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "version": APP_VERSION,
            "as_of": datetime.now().isoformat(timespec="seconds"),
        }

    return app


app = create_app()
