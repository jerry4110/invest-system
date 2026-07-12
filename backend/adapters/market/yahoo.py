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


def _yf_symbol(ticker: str) -> str:
    """한국형 코드 → 야후 심볼 (.KS 우선, 코스닥 .KQ 폴백은 호출부에서)."""
    if len(ticker) == 6 and any(c.isdigit() for c in ticker):
        return f"{ticker}.KS"
    return ticker


def get_valuation(ticker: str) -> dict:
    """PER·PBR·EV/EBITDA·PEG (FR-04-02 밸류에이션). 없으면 None — 추정 금지."""
    import yfinance as yf

    for symbol in (_yf_symbol(ticker),
                   f"{ticker}.KQ" if _yf_symbol(ticker).endswith(".KS") else None):
        if symbol is None:
            continue
        info = yf.Ticker(symbol).info or {}
        if info.get("trailingPE") or info.get("priceToBook") or info.get("marketCap"):
            return {
                "per": info.get("trailingPE"),
                "pbr": info.get("priceToBook"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "peg": info.get("trailingPegRatio") or info.get("pegRatio"),
                "market_cap": info.get("marketCap"),
                "symbol": symbol,
            }
    return {}


def get_balance(ticker: str, years: int = 3) -> dict[int, dict]:
    """해외 종목 재무상태표 (연도별) — 항목 없으면 생략."""
    import pandas as pd
    import yfinance as yf

    df = yf.Ticker(ticker).balance_sheet
    if df is None or df.empty:
        return {}
    mapping = {"Total Assets": "total_assets",
               "Total Liabilities Net Minority Interest": "total_liabilities",
               "Stockholders Equity": "total_equity",
               "Current Assets": "current_assets",
               "Current Liabilities": "current_liabilities"}
    out: dict[int, dict] = {}
    for col in sorted(df.columns)[-years:]:
        row = {}
        for acc, field in mapping.items():
            if acc in df.index and not pd.isna(df.loc[acc, col]):
                row[field] = int(df.loc[acc, col])
        if row:
            out[col.year] = row
    return out


def fetch_ohlcv(ticker: str, days: int = 180) -> list[dict]:
    """일봉 OHLCV (차트·기술 분석용). 한국형 코드는 .KS→.KQ 폴백."""
    import yfinance as yf

    for symbol in (_yf_symbol(ticker),
                   f"{ticker}.KQ" if _yf_symbol(ticker).endswith(".KS") else None):
        if symbol is None:
            continue
        df = yf.Ticker(symbol).history(period=f"{days + 30}d", interval="1d", auto_adjust=True)
        if df is None or df.empty:
            continue
        out = []
        for idx, row in df.tail(days).iterrows():
            out.append({"date": idx.date().isoformat(), "open": float(row["Open"]),
                        "high": float(row["High"]), "low": float(row["Low"]),
                        "close": float(row["Close"]), "volume": int(row["Volume"])})
        return out
    raise RuntimeError(f"시세 데이터 없음: {ticker}")
