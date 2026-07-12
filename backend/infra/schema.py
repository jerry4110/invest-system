"""DB 스키마 — PRD_Phase1 §6. 모든 조회성 테이블에 as_of(기준시각, NFR-04)."""
from datetime import datetime, date

from sqlalchemy import (
    Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "account"
    id: Mapped[int] = mapped_column(primary_key=True)
    broker: Mapped[str] = mapped_column(String(50))            # 예: miraeasset
    account_no_masked: Mapped[str] = mapped_column(String(30)) # 뒷자리 마스킹 저장
    alias: Mapped[str] = mapped_column(String(50))
    adapter_type: Mapped[str] = mapped_column(String(20))      # api | file
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Holding(Base):
    __tablename__ = "holding"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    ticker: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(20))            # KRX | OVERSEAS | ...
    sector: Mapped[str] = mapped_column(String(50), default="")  # 산업 (파일 카테고리 초기값, FR-03-23)
    qty: Mapped[float] = mapped_column(Numeric(18, 6))       # 금액·수량은 Numeric (Codex 리뷰 반영)
    avg_price: Mapped[float] = mapped_column(Numeric(18, 4))
    buy_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    cur_price: Mapped[float] = mapped_column(Numeric(18, 4))
    eval_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    pnl_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    pnl_pct: Mapped[float] = mapped_column(Float)
    as_of: Mapped[datetime] = mapped_column(DateTime)


class CashBalance(Base):
    __tablename__ = "cash_balance"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    currency: Mapped[str] = mapped_column(String(10), default="KRW")
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    as_of: Mapped[datetime] = mapped_column(DateTime)


class AssetSnapshot(Base):
    __tablename__ = "asset_snapshot"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True)      # 일별 1행 (FR-02-02)
    total_asset: Mapped[float] = mapped_column(Numeric(18, 2))
    total_buy: Mapped[float] = mapped_column(Numeric(18, 2))
    total_eval: Mapped[float] = mapped_column(Numeric(18, 2))
    total_pnl: Mapped[float] = mapped_column(Numeric(18, 2))
    total_cash: Mapped[float] = mapped_column(Numeric(18, 2))
    as_of: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)  # NFR-04 (Codex 리뷰 반영)


class MarketIndicator(Base):
    __tablename__ = "market_indicator"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), index=True)  # KOSPI, USDKRW, WTI ...
    name: Mapped[str] = mapped_column(String(50))
    date: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    as_of: Mapped[datetime] = mapped_column(DateTime)


class Strategy(Base):
    __tablename__ = "strategy"
    id: Mapped[int] = mapped_column(primary_key=True)
    persona: Mapped[str] = mapped_column(String(30))           # value|growth|trader (FR-01-01)
    guideline_text: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)   # FR-01-14
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class StrategyFile(Base):
    __tablename__ = "strategy_file"
    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategy.id"))
    filename: Mapped[str] = mapped_column(String(255))
    parsed_text: Mapped[str] = mapped_column(Text)             # FR-01-13
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TargetAllocation(Base):
    __tablename__ = "target_allocation"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)  # stock_pct, domestic_pct ...
    value_pct: Mapped[float] = mapped_column(Float)            # FR-01-15


class AppSetting(Base):
    __tablename__ = "app_setting"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))


class SecretStore(Base):
    __tablename__ = "secret_store"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    encrypted_value: Mapped[str] = mapped_column(Text)         # Fernet 암호문만 (NFR-01)


class JobLog(Base):
    __tablename__ = "job_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20))            # success | failed | running
    message: Mapped[str] = mapped_column(Text, default="")


class Transaction(Base):
    """Phase 1은 스키마만 생성 — 수집은 Phase 2 M6 (PRD_Phase1 §6 주석)."""
    __tablename__ = "transaction"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    ticker: Mapped[str] = mapped_column(String(20))
    side: Mapped[str] = mapped_column(String(10))              # buy | sell
    qty: Mapped[float] = mapped_column(Numeric(18, 6))
    price: Mapped[float] = mapped_column(Numeric(18, 4))
    executed_at: Mapped[datetime] = mapped_column(DateTime)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")        # 판단 근거 (FR-06-03)


class LlmUsage(Base):
    """LLM 호출 비용 기록 (T-21, D-015 월 상한 가드)."""
    __tablename__ = "llm_usage"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    model: Mapped[str] = mapped_column(String(50))
    prompt_name: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float)


class AnalysisResult(Base):
    """종목분석 이력 (FR-04-37) — 과거 분석과 비교용."""
    __tablename__ = "analysis_result"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    kind: Mapped[str] = mapped_column(String(20))   # comprehensive | debate | deep
    base_date: Mapped[str] = mapped_column(String(10))
    content_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
