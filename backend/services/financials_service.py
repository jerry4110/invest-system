"""재무 데이터 라우팅 (T-22) — 국내(숫자 코드)=DART, 해외=yfinance."""
from datetime import datetime


def _dart_financials(ticker: str) -> list[dict]:
    from backend.adapters.market.dart import DartClient
    return DartClient().get_major_financials(ticker)


def _yahoo_financials(ticker: str) -> list[dict]:
    from backend.adapters.market.yahoo import get_financials
    return get_financials(ticker)


def get_financials(ticker: str) -> dict:
    domestic = ticker.isdigit() or (len(ticker) == 6 and ticker.isalnum()
                                    and any(c.isdigit() for c in ticker))
    fin = _dart_financials(ticker) if domestic else _yahoo_financials(ticker)
    return {"ticker": ticker, "source": "DART" if domestic else "yfinance",
            "financials": fin,
            "as_of": datetime.now().isoformat(timespec="seconds")}
