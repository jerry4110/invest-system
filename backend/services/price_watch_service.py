"""보유종목 급등락 감시 (M8, FR-08-03·06) — 아침 배치에서 호출, 실패 격리."""
import logging

from backend.infra.db import get_session
from backend.infra.schema import AppSetting, Holding

logger = logging.getLogger(__name__)
DEFAULT_THRESHOLD = 5.0


def get_threshold() -> float:
    with get_session() as s:
        row = s.get(AppSetting, "price_move_threshold_pct")
    return float(row.value) if row else DEFAULT_THRESHOLD


def set_threshold(pct: float) -> None:
    with get_session() as s:
        s.merge(AppSetting(key="price_move_threshold_pct", value=str(pct)))
        s.commit()


def _load_change_pct(tickers: list[str]) -> dict[str, float]:
    """종목별 전일 대비 등락률 (야후 2일 종가)."""
    from backend.adapters.market.yahoo import fetch_ohlcv
    out = {}
    for t in tickers:
        try:
            bars = fetch_ohlcv(t, 5)
            if len(bars) >= 2 and bars[-2]["close"]:
                out[t] = round((bars[-1]["close"] / bars[-2]["close"] - 1) * 100, 2)
        except Exception as e:
            logger.warning("등락률 조회 실패(격리): %s — %s", t, e)
    return out


def check_price_moves() -> dict:
    """임계값(±N%) 초과 보유종목 → 알림 (일중 중복은 alert_service가 방지)."""
    threshold = get_threshold()
    with get_session() as s:
        holdings = {h.ticker: h.name for h in s.query(Holding).all()}
    if not holdings:
        return {"alerted": [], "checked": 0}
    try:
        changes = _load_change_pct(list(holdings))
    except Exception as e:
        logger.warning("급등락 감시 실패(격리): %s", e)
        return {"alerted": [], "checked": 0, "error": str(e)}

    from backend.services.alert_service import create_alert
    alerted = []
    for ticker, pct in changes.items():
        if abs(pct) >= threshold:
            name = holdings.get(ticker, ticker)
            arrow = "급등" if pct > 0 else "급락"
            create_alert("price_move",
                         f"{name} {'+' if pct > 0 else ''}{pct}% {arrow}",
                         f"전일 대비 {pct}% (임계값 ±{threshold}%)")
            alerted.append(ticker)
    return {"alerted": sorted(alerted), "checked": len(changes),
            "threshold_pct": threshold}
