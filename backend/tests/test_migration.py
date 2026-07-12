"""회귀: 스키마에 컬럼이 추가돼도 기존 DB가 자동 마이그레이션돼야 한다 (500 에러 재발 방지)."""
import sqlite3

from sqlalchemy import inspect

from backend.infra import db as db_mod


def test_missing_column_auto_added(tmp_path, monkeypatch):
    # 구버전 DB 시뮬레이션: sector 없는 holding 테이블
    db_path = tmp_path / "old.db"
    con = sqlite3.connect(db_path)
    con.execute("""CREATE TABLE holding (
        id INTEGER PRIMARY KEY, account_id INTEGER, ticker VARCHAR, name VARCHAR,
        market VARCHAR, qty NUMERIC, avg_price NUMERIC, buy_amount NUMERIC,
        cur_price NUMERIC, eval_amount NUMERIC, pnl_amount NUMERIC,
        pnl_pct FLOAT, as_of DATETIME)""")
    con.execute("""INSERT INTO holding VALUES
        (1, 1, '005930', '삼성전자', 'KRX', 10, 1, 1, 1, 1, 1, 0, '2026-07-12')""")
    con.commit()
    con.close()

    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    engine = db_mod.init_db(str(db_path))

    cols = {c["name"] for c in inspect(engine).get_columns("holding")}
    assert "sector" in cols                       # 자동 추가됨
    # 기존 데이터 보존 + 신규 컬럼 조회 가능 (500 재현 방지)
    from backend.infra.schema import Holding
    with db_mod.get_session() as s:
        row = s.query(Holding).one()
        assert row.name == "삼성전자" and (row.sector or "") == ""
