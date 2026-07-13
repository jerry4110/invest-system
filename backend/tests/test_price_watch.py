"""T-34 수용 기준: 보유종목 급등락 감시(FR-08-03) — 임계값 설정·알림·격리."""
import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod

CSV = """종목명,종목코드,보유수량,평균매입가,현재가,매입금액,평가금액,평가손익,수익률
삼성전자,005930,100,70000,75000,7000000,7500000,500000,7.14
카카오,035720,50,40000,50000,2000000,2500000,500000,25.0
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    c = TestClient(main_mod.create_app())
    c.post("/api/portfolio/upload",
           files={"file": ("잔고.csv", CSV.encode("utf-8-sig"), "text/csv")})
    return c


def test_price_watch_alerts_over_threshold(client, monkeypatch):
    """전일 대비 ±5%(기본) 초과 종목만 알림."""
    from backend.services import price_watch_service as svc
    from backend.infra.schema import Alert

    changes = {"005930": +6.2, "035720": -1.0}   # 삼성만 임계 초과
    monkeypatch.setattr(svc, "_load_change_pct", lambda tickers: changes)
    result = svc.check_price_moves()
    assert result["alerted"] == ["005930"]
    with db_mod.get_session() as s:
        alerts = s.query(Alert).filter_by(kind="price_move").all()
        assert len(alerts) == 1
        assert "삼성전자" in alerts[0].title and "+6.2" in alerts[0].title


def test_threshold_setting_respected(client, monkeypatch):
    """FR-08-06: 임계값 설정 반영 (설정 3% → 카카오 -4%도 알림)."""
    from backend.services import price_watch_service as svc
    from backend.infra.schema import Alert

    client.put("/api/settings", json={})   # settings 초기화 경유
    svc.set_threshold(3.0)
    monkeypatch.setattr(svc, "_load_change_pct",
                        lambda tickers: {"005930": +1.0, "035720": -4.0})
    result = svc.check_price_moves()
    assert result["alerted"] == ["035720"]
    assert svc.get_threshold() == 3.0


def test_load_failure_isolated(client, monkeypatch):
    from backend.services import price_watch_service as svc
    monkeypatch.setattr(svc, "_load_change_pct",
                        lambda tickers: (_ for _ in ()).throw(ConnectionError("down")))
    result = svc.check_price_moves()                        # 예외 없이 격리
    assert result["alerted"] == [] and "down" in result["error"]
