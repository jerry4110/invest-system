"""FastAPI 엔트리 — 실행: uvicorn backend.main:app --port 8000"""
from datetime import datetime

from fastapi import FastAPI

APP_VERSION = "0.1.0"  # Phase 1 / T-01


def create_app() -> FastAPI:
    app = FastAPI(title="개인투자관리시스템 API", version=APP_VERSION)

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "version": APP_VERSION,
            "as_of": datetime.now().isoformat(timespec="seconds"),
        }

    return app


app = create_app()
