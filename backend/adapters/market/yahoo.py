"""yfinance 어댑터 — 일별 시계열 조회. 반환: [(date, close)] 오름차순."""
from datetime import date


def fetch_series(symbol: str, days: int = 30) -> list[tuple[date, float]]:
    import yfinance as yf  # 지연 import (테스트에서 불필요한 네트워크 의존 방지)
    df = yf.Ticker(symbol).history(period=f"{days + 10}d", interval="1d", auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"yfinance 응답 없음: {symbol}")
    closes = df["Close"].dropna().tail(days)
    return [(idx.date(), float(v)) for idx, v in closes.items()]
