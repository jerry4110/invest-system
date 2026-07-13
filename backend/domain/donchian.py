"""Donchian Channel 추세추종 전략 엔진 (M7-2, FR-07-11~13) — 순수 계산.

규칙(기능요건정의서): 매수 = entry_n일 채널 상단 돌파, 매도 = exit_n일 채널 하단 돌파,
스탑로스 = 진입가 대비 -stop_pct% (스탑 우선). 파라미터 조정 가능.
"""


def donchian_channels(ohlcv: list[dict], n: int = 20) -> tuple[list, list]:
    """직전 n일(당일 제외) 최고가/최저가. 데이터 부족 구간은 None."""
    upper, lower = [], []
    for i in range(len(ohlcv)):
        if i < n:
            upper.append(None)
            lower.append(None)
        else:
            window = ohlcv[i - n:i]
            upper.append(max(b["high"] for b in window))
            lower.append(min(b["low"] for b in window))
    return upper, lower


def generate_positions(ohlcv: list[dict], entry_n: int = 20, exit_n: int = 10,
                       stop_pct: float = 8.0) -> list[int]:
    """포지션 시계열(0/1) — run_position_backtest 입력용."""
    entry_up, _ = donchian_channels(ohlcv, entry_n)
    _, exit_low = donchian_channels(ohlcv, exit_n)
    positions, holding, entry_price = [], 0, None
    for i, bar in enumerate(ohlcv):
        close = bar["close"]
        if holding == 0:
            if entry_up[i] is not None and close > entry_up[i]:
                holding, entry_price = 1, close
        else:
            stop_hit = entry_price and close <= entry_price * (1 - stop_pct / 100)
            exit_hit = exit_low[i] is not None and close < exit_low[i]
            if stop_hit or exit_hit:
                holding, entry_price = 0, None
        positions.append(holding)
    return positions


def analyze_today(ohlcv: list[dict], entry_n: int = 20, exit_n: int = 10) -> dict:
    """최신 봉 기준 시그널 (FR-07-14 일일 감시용)."""
    if len(ohlcv) < entry_n + 1:
        return {"signal": None, "reason": f"데이터 부족 ({entry_n + 1}일 이상 필요)",
                "upper": None, "lower": None, "close": None}
    entry_up, _ = donchian_channels(ohlcv, entry_n)
    _, exit_low = donchian_channels(ohlcv, exit_n)
    close = ohlcv[-1]["close"]
    upper, lower = entry_up[-1], exit_low[-1]
    if upper is not None and close > upper:
        signal, reason = "BUY", f"종가 {close:,.2f} > {entry_n}일 채널 상단 {upper:,.2f}"
    elif lower is not None and close < lower:
        signal, reason = "SELL", f"종가 {close:,.2f} < {exit_n}일 채널 하단 {lower:,.2f}"
    else:
        signal, reason = None, "채널 내 — 시그널 없음"
    return {"signal": signal, "reason": reason, "upper": upper, "lower": lower,
            "close": close, "date": ohlcv[-1]["date"]}
