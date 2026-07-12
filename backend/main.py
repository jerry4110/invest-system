"""FastAPI 엔트리 — 실행: uvicorn backend.main:app --port 8000"""
from datetime import datetime

from fastapi import FastAPI

from backend.api.dashboard import router as dashboard_router
from backend.api.portfolio import router as portfolio_router
from backend.api.settings import router as settings_router
from backend.api.strategy import router as strategy_router

APP_VERSION = "0.5.0"  # Phase 1 / T-09


def create_app() -> FastAPI:
    app = FastAPI(title="개인투자관리시스템 API", version=APP_VERSION)
    app.include_router(settings_router)
    app.include_router(dashboard_router)
    app.include_router(portfolio_router)
    app.include_router(strategy_router)

    @app.on_event("startup")
    def _start_watcher():
        from backend.infra.db import init_db
        from backend.infra.watcher import start_watcher
        init_db()
        start_watcher()  # D-013 폴더 감시

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "version": APP_VERSION,
            "as_of": datetime.now().isoformat(timespec="seconds"),
        }

    return app


app = create_app()
