"""SQLAlchemy 엔진·세션 팩토리."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.infra.config import load_config
from backend.infra.schema import Base

_engine = None
_SessionLocal: sessionmaker | None = None


def init_db(db_path: str | None = None):
    """엔진 생성 + 테이블 생성. 앱 시작 시 1회 호출."""
    global _engine, _SessionLocal
    path = db_path or load_config().db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{path}", echo=False)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session() -> Session:
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()
