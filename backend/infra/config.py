"""애플리케이션 설정 로더 (비민감 설정 전용 — 키는 secret_store, constitution §2.5)."""
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULTS = {
    "refresh_time": "08:00",   # FR-00-21
    "api_port": 8000,
    "db_path": "data/invest.db",
}


@dataclass(frozen=True)
class AppConfig:
    refresh_time: str
    api_port: int
    db_path: str


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    """config.yaml을 읽고, 없거나 항목이 빠지면 기본값을 적용한다."""
    merged = dict(DEFAULTS)
    p = Path(path)
    if p.exists():
        loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        merged.update({k: v for k, v in loaded.items() if k in DEFAULTS})
    return AppConfig(**merged)
