"""T-01 수용 기준: config.yaml 로드, 기본값 제공."""
from backend.infra.config import load_config


def test_config_defaults(tmp_path):
    cfg = load_config(tmp_path / "none.yaml")  # 파일 없어도 기본값
    assert cfg.refresh_time == "08:00"
    assert cfg.api_port == 8000
    assert cfg.db_path.endswith(".db")


def test_config_override(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("refresh_time: '07:30'\napi_port: 9000\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.refresh_time == "07:30"
    assert cfg.api_port == 9000
