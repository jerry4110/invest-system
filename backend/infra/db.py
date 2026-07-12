"""SQLAlchemy 엔진·세션 팩토리."""
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from backend.infra.config import load_config
from backend.infra.schema import Base

_engine = None
_SessionLocal: sessionmaker | None = None


def init_db(db_path: str | None = None):
    """엔진 생성 + 테이블 생성. 앱 시작 시 1회 호출.

    이미 초기화된 상태에서 경로 없이 재호출되면 기존 엔진 유지 (멱등 — 테스트 격리 보호).
    """
    global _engine, _SessionLocal
    if db_path is None and _engine is not None:
        return _engine
    path = db_path or load_config().db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{path}", echo=False)
    Base.metadata.create_all(_engine)
    _auto_migrate(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session() -> Session:
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()


def _auto_migrate(engine) -> None:
    """스키마에 새로 추가된 컬럼을 기존 DB에 반영 (SQLite ADD COLUMN).

    코드 갱신 후 구버전 DB에서 'no such column' 500 오류가 나는 문제의 근본 해결.
    컬럼 삭제·타입 변경은 다루지 않음 (필요 시 별도 마이그레이션).
    """
    import logging
    logger = logging.getLogger(__name__)
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in insp.get_table_names():
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                coltype = col.type.compile(engine.dialect)
                default = ""
                if col.default is not None and getattr(col.default, "arg", None) is not None \
                        and not callable(col.default.arg):
                    val = col.default.arg
                    default = f" DEFAULT '{val}'" if isinstance(val, str) else f" DEFAULT {val}"
                conn.execute(text(
                    f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {coltype}{default}'))
                logger.info("DB 마이그레이션: %s.%s 컬럼 추가", table.name, col.name)
