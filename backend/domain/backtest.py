"""백테스트 성과지표 엔진 (M7-1, FR-07-03) — 순수 계산, 금액·비율은 검증된 공식만.

원칙: 산출 불가(변동 없음 등)면 None — 추정 금지 (constitution §2.4·2.7).
"""
import math
from datetime import date


def metrics_from_equity(dates: list[date], values: list[float]) -> dict:
    """자산곡선 → 누적수익률·CAGR·MDD·MAR·샤프."""
    if len(values) < 2 or values[0] <= 0:
        return {"cumulative_return_pct": None, "cagr_pct": None, "mdd_pct": None,
                "mar": None, "sharpe": None}

    cumulative = (values[-1] / values[0] - 1) * 100

    years = (dates[-1] - dates[0]).days / 365.0
    cagr = ((values[-1] / values[0]) ** (1 / years) - 1) * 100 if years > 0 else None

    peak, mdd = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak * 100)

    mar = round(cagr / mdd, 4) if cagr is not None and mdd > 0 else None

    rets = [(b / a - 1) for a, b in zip(values[:-1], values[1:]) if a > 0]
    sharpe = None
    if len(rets) >= 2:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        std = math.sqrt(var)
        if std > 0:
            periods_per_year = max(len(rets) / years, 1) if years > 0 else 252
            sharpe = round(mean / std * math.sqrt(periods_per_year), 4)

    return {"cumulative_return_pct": round(cumulative, 2),
            "cagr_pct": round(cagr, 2) if cagr is not None else None,
            "mdd_pct": round(mdd, 2), "mar": mar, "sharpe": sharpe}


def trade_stats(trades: list[dict]) -> dict:
    """거래 목록 → 승률·손익비 (FR-07-03)."""
    if not trades:
        return {"trades": 0, "win_rate_pct": None, "payoff_ratio": None}
    wins = [t["pnl_pct"] for t in trades if t["pnl_pct"] > 0]
    losses = [-t["pnl_pct"] for t in trades if t["pnl_pct"] < 0]
    return {
        "trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "payoff_ratio": round((sum(wins) / len(wins)) / (sum(losses) / len(losses)), 4)
                        if wins and losses else None,
    }


def run_position_backtest(dates: list[date], closes: list[float],
                          positions: list[int]) -> dict:
    """포지션 시계열(0/1) 기반 백테스트 — Donchian 등 전략 엔진의 공통 실행기.

    반환: equity curve + 거래 목록 + 지표. 수수료·슬리피지 미반영(고지 필수).
    """
    equity, eq = [1.0], 1.0
    trades, entry = [], None
    for i in range(1, len(closes)):
        if positions[i - 1] == 1:
            eq *= closes[i] / closes[i - 1]
        equity.append(eq)
        if positions[i] == 1 and positions[i - 1] == 0:
            entry = closes[i]
        elif positions[i] == 0 and positions[i - 1] == 1 and entry:
            trades.append({"pnl_pct": round((closes[i] / entry - 1) * 100, 2),
                           "exit_date": dates[i].isoformat()})
            entry = None
    metrics = metrics_from_equity(dates, equity)
    metrics.update(trade_stats(trades))
    return {"equity": equity, "trades": trades, "metrics": metrics}
