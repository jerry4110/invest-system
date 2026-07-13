"""Donchian 서비스 (M7-2) — 백테스트·일일 코스피 감시 (FR-07-11~15)."""
import json
import logging
from datetime import date, datetime

from backend.domain.backtest import run_position_backtest
from backend.domain.donchian import analyze_today, generate_positions

logger = logging.getLogger(__name__)


def _load_ohlcv(ticker: str, days: int) -> list[dict]:
    from backend.adapters.market.yahoo import fetch_ohlcv
    return fetch_ohlcv(ticker, days)


def _load_kospi(days: int = 80) -> list[dict]:
    from backend.adapters.market.yahoo import fetch_ohlcv
    return fetch_ohlcv("^KS11", days)


def backtest(ticker: str = "KOSPI", entry_n: int = 20, exit_n: int = 10,
             stop_pct: float = 8.0, days: int = 730) -> dict:
    """Donchian 백테스트 — 시나리오 저장 (FR-07-05·13)."""
    from backend.services.backtest_service import DISCLAIMER, _downsample, _save_run

    symbol = "^KS11" if ticker.upper() == "KOSPI" else ticker
    ohlcv = _load_ohlcv(symbol, days)
    dates = [date.fromisoformat(b["date"]) for b in ohlcv]
    closes = [b["close"] for b in ohlcv]
    positions = generate_positions(ohlcv, entry_n, exit_n, stop_pct)
    result = run_position_backtest(dates, closes, positions)
    params = {"entry_n": entry_n, "exit_n": exit_n, "stop_pct": stop_pct, "ticker": ticker}
    run_id = _save_run(f"Donchian {ticker} ({entry_n}/{exit_n}/-{stop_pct}%)",
                       "donchian", params, result["metrics"], dates, result["equity"])
    return {"run_id": run_id, "params": params, "metrics": result["metrics"],
            "trades": result["trades"][-20:],
            "curve": _downsample(dates, result["equity"], 300),
            "as_of": datetime.now().isoformat(timespec="seconds"),
            "disclaimer": DISCLAIMER}


def daily_check() -> dict:
    """FR-07-14: 코스피 일일 Donchian 감시 → 시그널 시 알림 (이력 = alert)."""
    result = analyze_today(_load_kospi())
    if result["signal"]:
        from backend.services.alert_service import create_alert
        kind_kr = "매수" if result["signal"] == "BUY" else "매도"
        create_alert("donchian",
                     f"코스피 Donchian {kind_kr} 시그널",
                     f"{result['reason']} (기준일 {result.get('date')})")
    logger.info("Donchian 일일 점검: %s", result["signal"] or "시그널 없음")
    return result
