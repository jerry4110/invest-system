"""거래내역 파일 파서 (FR-06-01, D-013 파일 기반) — 잔고 파서와 동일한 헤더 감지 방식."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

from backend.adapters.broker.file_upload import ParseError, _clean_number, _read_raw


@dataclass(frozen=True)
class TradeDTO:
    executed_at: datetime
    ticker: str
    name: str
    side: str          # buy | sell
    qty: Decimal
    price: Decimal
    fee: Decimal
    fixed_pnl: Decimal | None = None   # 증권사 계산 손익 (있으면 재계산 대신 사용)


TRADE_HEADERS = {
    "date":   ["거래일자", "체결일자", "주문일자", "일자", "거래일"],
    "ticker": ["종목코드", "종목번호", "코드"],
    "name":   ["종목명", "종목", "상품명"],
    "side":   ["구분", "매매구분", "거래구분", "매수매도"],
    "qty":    ["수량", "체결수량", "거래수량"],
    "price":  ["단가", "체결단가", "거래단가", "체결가"],
    "fee":    ["수수료", "수수료합", "제비용"],
}
_REQUIRED = {"date", "name", "side", "qty", "price"}
BUY_WORDS = ("매수", "buy", "매입")
SELL_WORDS = ("매도", "sell")


def _parse_aggregate_format(df) -> list[TradeDTO] | None:
    """미래에셋 '기간 중 매매' 집계 형식 (2026-07-15 실파일): 2행 헤더, 매수/매도 병렬.

    컬럼: 일자,종목명,[매수]수량,평균단가,매수금액,[매도]수량,평균단가,매도금액,매매비용,손익금액,수익률
    """
    row0 = [str(c).strip() if not pd.isna(c) else "" for c in df.iloc[0]]
    if "기간 중 매수" not in row0 or "기간 중 매도" not in row0:
        return None
    trades = []
    for _, row in df.iloc[2:].iterrows():
        raw_d = row.iloc[0]
        name = str(row.iloc[1]).strip() if not pd.isna(row.iloc[1]) else ""
        if pd.isna(raw_d) or not name or name == "nan":
            continue
        executed = pd.to_datetime(str(raw_d).replace("/", "-")).to_pydatetime()
        buy_qty = _clean_number(row.iloc[2])
        sell_qty = _clean_number(row.iloc[5])
        fee = _clean_number(row.iloc[8]) if len(row) > 8 else Decimal(0)
        pnl = _clean_number(row.iloc[9]) if len(row) > 9 else Decimal(0)
        if buy_qty > 0:
            trades.append(TradeDTO(executed_at=executed, ticker=name, name=name,
                                   side="buy", qty=buy_qty,
                                   price=_clean_number(row.iloc[3]), fee=Decimal(0)))
        if sell_qty > 0:
            trades.append(TradeDTO(executed_at=executed, ticker=name, name=name,
                                   side="sell", qty=sell_qty,
                                   price=_clean_number(row.iloc[6]), fee=fee,
                                   fixed_pnl=pnl))
    return trades if trades else None


def parse_trades_file(path: str | Path) -> list[TradeDTO]:
    df = _read_raw(Path(path))
    agg = _parse_aggregate_format(df)
    if agg is not None:
        return sorted(agg, key=lambda t: t.executed_at)
    header_row, col = None, {}
    for i in range(min(len(df), 20)):
        row = [str(c).strip() if not pd.isna(c) else "" for c in df.iloc[i]]
        found = {f: j for f, names in TRADE_HEADERS.items()
                 for j, cell in enumerate(row) if cell in names}
        if _REQUIRED <= set(found):
            header_row, col = i, found
            break
    if header_row is None:
        raise ParseError("거래내역 파일에서 컬럼(거래일자·종목명·구분·수량·단가)을 찾지 못했습니다")

    trades = []
    for _, row in df.iloc[header_row + 1:].iterrows():
        def get(f, default=""):
            j = col.get(f)
            return row.iloc[j] if j is not None and j < len(row) else default

        name = str(get("name")).strip()
        if not name or name == "nan":
            continue
        side_raw = str(get("side")).strip().lower()
        side = ("buy" if any(w in side_raw for w in BUY_WORDS)
                else "sell" if any(w in side_raw for w in SELL_WORDS) else None)
        if side is None:
            continue  # 입출금 등 매매 외 행 스킵
        trades.append(TradeDTO(
            executed_at=pd.to_datetime(str(get("date"))).to_pydatetime(),
            ticker=str(get("ticker", "")).strip() or name,
            name=name, side=side,
            qty=_clean_number(get("qty")),
            price=_clean_number(get("price")),
            fee=_clean_number(get("fee")) if col.get("fee") is not None else Decimal("0"),
        ))
    if not trades:
        raise ParseError("거래내역에서 매매 행을 찾지 못했습니다")
    return sorted(trades, key=lambda t: t.executed_at)
