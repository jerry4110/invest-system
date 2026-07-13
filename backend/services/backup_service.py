"""DB 백업·복원 (FR-10-05, T-30). 복원 시 엔진을 내렸다가 재초기화한다."""
import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
BACKUP_DIR = Path("data/backup")


def _db_path() -> Path:
    from backend.infra.config import load_config
    return Path(load_config().db_path)


def create_backup() -> dict:
    src = _db_path()
    if not src.exists():
        raise FileNotFoundError("DB 파일이 아직 없습니다")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"invest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(src, BACKUP_DIR / filename)
    logger.info("DB 백업 생성: %s", filename)
    return {"filename": filename,
            "created_at": datetime.now().isoformat(timespec="seconds")}


def list_backups() -> list[dict]:
    if not BACKUP_DIR.is_dir():
        return []
    out = []
    for f in sorted(BACKUP_DIR.glob("invest_*.db"), reverse=True):
        st = f.stat()
        out.append({"filename": f.name, "size_kb": round(st.st_size / 1024, 1),
                    "created_at": datetime.fromtimestamp(st.st_mtime)
                    .isoformat(timespec="seconds")})
    return out


def restore_backup(filename: str) -> None:
    """백업 파일로 DB 교체 — 파일명 검증(경로 탈출 방지) 후 엔진 재초기화."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError("잘못된 파일명입니다")
    src = BACKUP_DIR / filename
    if not src.exists():
        raise FileNotFoundError(f"백업 파일 없음: {filename}")
    from backend.infra import db as db_mod
    dst = _db_path()
    if db_mod._engine is not None:
        db_mod._engine.dispose()
        db_mod._engine = None
        db_mod._SessionLocal = None
    shutil.copy2(src, dst)
    db_mod.init_db(str(dst))
    logger.warning("DB 복원 완료: %s → %s", filename, dst)
