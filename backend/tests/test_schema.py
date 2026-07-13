"""T-01 수용 기준: PRD_Phase1 §6의 12개 테이블이 생성된다."""
from sqlalchemy import create_engine, inspect

from backend.infra.schema import Base

EXPECTED_TABLES = {
    "account", "holding", "cash_balance", "asset_snapshot",
    "market_indicator", "strategy", "strategy_file", "target_allocation",
    "app_setting", "secret_store", "job_log", "transaction", "llm_usage", "analysis_result", "report", "alert", "backtest_run",
}


def test_all_tables_created():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES <= tables, f"누락: {EXPECTED_TABLES - tables}"


import pytest


@pytest.mark.parametrize("table", ["holding", "cash_balance", "asset_snapshot", "market_indicator"])
def test_lookup_tables_have_as_of_column(table):
    """NFR-04: 시계열·조회 데이터 테이블 전체에 기준시각(as_of) 필수 (Codex 리뷰 반영)."""
    cols = {c.name for c in Base.metadata.tables[table].columns}
    assert "as_of" in cols, f"{table}에 as_of 없음"


def test_money_columns_are_numeric():
    """금액 컬럼은 부동소수점 누적오차 방지 위해 Numeric (Codex 리뷰 반영)."""
    from sqlalchemy import Numeric
    for table, col in [("holding", "buy_amount"), ("holding", "eval_amount"),
                       ("cash_balance", "amount"), ("asset_snapshot", "total_asset")]:
        assert isinstance(Base.metadata.tables[table].columns[col].type, Numeric)
