"""로깅 설정 — 민감정보(키·계좌번호) 출력 금지 (constitution §2.5)."""
import logging
from pathlib import Path


def setup_logging(log_dir: str = "data/logs") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{log_dir}/app.log", encoding="utf-8"),
        ],
    )
