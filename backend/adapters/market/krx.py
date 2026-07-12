"""KRX 수급·공매도 어댑터 (D-016) — pykrx, 로그인은 secret_store의 krx_id/krx_pw."""
import logging
import os
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def _login_env() -> None:
    from backend.services.settings_service import get_secret
    kid, kpw = get_secret("krx_id"), get_secret("krx_pw")
    if not kid or not kpw:
        raise RuntimeError("krx_id/krx_pw가 없습니다 — 설정 > API 키에 등록하세요 (data.krx.co.kr 계정)")
    os.environ["KRX_ID"], os.environ["KRX_PW"] = kid, kpw


def get_investor_flows(ticker: str, days: int = 60) -> list[dict]:
    """투자자별 순매수 대금 (FR-04-14) — 개인/기관/외국인, 일별."""
    _login_env()
    from pykrx import stock
    end = date.today()
    start = end - timedelta(days=days + 40)
    df = stock.get_market_trading_value_by_date(
        start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), ticker)
    out = []
    for idx, row in df.tail(days).iterrows():
        out.append({"date": idx.date().isoformat() if hasattr(idx, "date") else str(idx),
                    "individual": int(row.get("개인", 0)),
                    "institution": int(row.get("기관합계", row.get("기관", 0))),
                    "foreign": int(row.get("외국인합계", row.get("외국인", 0)))})
    return out


def get_short_interest(ticker: str, days: int = 60) -> list[dict]:
    """공매도 잔고·비중 (FR-04-15)."""
    _login_env()
    from pykrx import stock
    end = date.today()
    start = end - timedelta(days=days + 40)
    df = stock.get_shorting_balance_by_date(
        start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), ticker)
    out = []
    for idx, row in df.tail(days).iterrows():
        out.append({"date": idx.date().isoformat() if hasattr(idx, "date") else str(idx),
                    "balance": int(row.get("공매도잔고", row.get("잔고수량", 0))),
                    "ratio_pct": float(row.get("비중", 0))})
    return out
