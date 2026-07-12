"""BrokerAdapter 추상 인터페이스 (FR-03-03, NFR-03).

첫 구현체는 파일 기반(file_upload.py, D-013). 증권사 API 어댑터는 향후 추가 옵션.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class HoldingDTO:
    name: str
    ticker: str
    qty: Decimal
    avg_price: Decimal
    buy_amount: Decimal
    cur_price: Decimal
    eval_amount: Decimal
    pnl_amount: Decimal
    pnl_pct: float
    market: str = "UNKNOWN"
    sector: str = ""


class BrokerAdapter(ABC):
    @abstractmethod
    def get_holdings(self) -> list[HoldingDTO]: ...
