"""yfinance 어댑터 — 일별 시계열 조회. 반환: [(date, close)] 오름차순."""
from datetime import date


def fetch_series(symbol: str, days: int = 30) -> list[tuple[date, float]]:
    import yfinance as yf  # 지연 import (테스트에서 불필요한 네트워크 의존 방지)
    df = yf.Ticker(symbol).history(period=f"{days + 10}d", interval="1d", auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"yfinance 응답 없음: {symbol}")
    closes = df["Close"].dropna().tail(days)
    return [(idx.date(), float(v)) for idx, v in closes.items()]


def get_financials(symbol: str, years: int = 3) -> list[dict]:
    """해외 종목 연간 재무 (FR-00-05) — 매출·영업이익·순이익, 연도 오름차순."""
    import pandas as pd
    import yfinance as yf

    df = yf.Ticker(symbol).income_stmt  # 컬럼=연도(Timestamp), 행=계정
    if df is None or df.empty:
        raise RuntimeError(f"yfinance 재무 없음: {symbol}")
    mapping = {"Total Revenue": "revenue", "Operating Income": "operating_profit",
               "Net Income": "net_income"}
    out = []
    for col in sorted(df.columns)[-years:]:
        row = {"year": col.year}
        for acc, field in mapping.items():
            if acc in df.index and not pd.isna(df.loc[acc, col]):
                row[field] = int(df.loc[acc, col])
        if len(row) > 1:
            out.append(row)
    return out
