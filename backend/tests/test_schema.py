"""T-01 수용 기준: PRD_Phase1 §6의 12개 테이블이 생성된다."""
from sqlalchemy import create_engine, inspect

from backend.infra.schema import Base

EXPECTED_TABLES = {
    "account", "holding", "cash_balance", "asset_snapshot",
    "market_indicator", "strategy", "strategy_file", "target_allocation",
    "app_setting", "secret_store", "job_log", "transaction",
}


def test_all_tables_created():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES <= tables, f"누락: {EXPECTED_TABLES - tables}"


def test_holding_has_as_of_column():
    """NFR-04: 시계열·조회 데이터에 기준시각(as_of) 필수."""
    cols = {c.name for c in Base.metadata.tables["holding"].columns}
    assert "as_of" in cols
    cols_mi = {c.name for c in Base.metadata.tables["market_indicator"].columns}
    assert "as_of" in cols_mi
