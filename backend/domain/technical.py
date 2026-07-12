"""기술적 분석 엔진 (분석 B, FR-04-11~16) — 순수 계산, LLM 아님.

원칙: 데이터 부족 시 None·'판단 보류' — 억지 판정 금지 (constitution §2.7).
"""


def sma(closes: list[float], n: int) -> float | None:
    if len(closes) < n:
        return None
    return round(sum(closes[-n:]) / n, 4)


def rsi(closes: list[float], n: int = 14) -> float | None:
    """Wilder RSI."""
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for prev, cur in zip(closes[:-1], closes[1:]):
        diff = cur - prev
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    for g, l in zip(gains[n:], losses[n:]):
        avg_gain = (avg_gain * (n - 1) + g) / n
        avg_loss = (avg_loss * (n - 1) + l) / n
    if avg_loss == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_gain / avg_loss), 2)


def _ema(closes: list[float], n: int) -> list[float]:
    k = 2 / (n + 1)
    out = [closes[0]]
    for c in closes[1:]:
        out.append(c * k + out[-1] * (1 - k))
    return out


def macd(closes: list[float]) -> dict | None:
    """MACD(12,26,9)."""
    if len(closes) < 35:
        return None
    line = [a - b for a, b in zip(_ema(closes, 12), _ema(closes, 26))]
    signal = _ema(line[25:], 9)
    return {"macd": round(line[-1], 4), "signal": round(signal[-1], 4),
            "histogram": round(line[-1] - signal[-1], 4)}


def _cross(closes: list[float], fast: int, slow: int, window: int = 5) -> str | None:
    """최근 window일 내 골든/데드크로스."""
    if len(closes) < slow + window:
        return None
    for i in range(-window, 0):
        f_now, s_now = sma(closes[:i or None], fast), sma(closes[:i or None], slow)
        f_prev, s_prev = sma(closes[:i - 1], fast), sma(closes[:i - 1], slow)
        if None in (f_now, s_now, f_prev, s_prev):
            continue
        if f_prev <= s_prev and f_now > s_now:
            return "골든크로스"
        if f_prev >= s_prev and f_now < s_now:
            return "데드크로스"
    return None


def analyze_technical(ohlcv: list[dict]) -> dict:
    """OHLCV → 지표 + 규칙 기반 종합 시그널 (FR-04-16)."""
    closes = [row["close"] for row in ohlcv]
    volumes = [row["volume"] for row in ohlcv]

    ma = {str(n): sma(closes, n) for n in (5, 20, 60, 120)}
    r = rsi(closes)
    m = macd(closes)
    cross = _cross(closes, 5, 20)

    alignment = None
    if all(ma[k] is not None for k in ("5", "20", "60", "120")):
        if ma["5"] > ma["20"] > ma["60"] > ma["120"]:
            alignment = "정배열"
        elif ma["5"] < ma["20"] < ma["60"] < ma["120"]:
            alignment = "역배열"
        else:
            alignment = "혼조"

    vol_surge = None
    if len(volumes) >= 60:
        recent, base = sum(volumes[-5:]) / 5, sum(volumes[-60:]) / 60
        vol_surge = round(recent / base, 2) if base else None

    score, reasons = 0, []
    if alignment == "정배열":
        score += 2; reasons.append("이동평균 정배열 (상승 추세)")
    elif alignment == "역배열":
        score -= 2; reasons.append("이동평균 역배열 (하락 추세)")
    if cross == "골든크로스":
        score += 1; reasons.append("최근 5일 내 골든크로스 (5/20일선)")
    elif cross == "데드크로스":
        score -= 1; reasons.append("최근 5일 내 데드크로스 (5/20일선)")
    # 역추세 시그널은 추세 필터 적용 — 추세와 반대 방향 오실레이터는 점수 미반영
    if r is not None:
        if r >= 70:
            if alignment != "정배열":
                score -= 1
            reasons.append(f"RSI {r} 과매수 구간 — 단기 조정 유의")
        elif r <= 30:
            if alignment != "역배열":
                score += 1
                reasons.append(f"RSI {r} 과매도 구간 — 반등 여지")
            else:
                reasons.append(f"RSI {r} 과매도 — 하락 추세 중이므로 반등 신호로 보지 않음")
    if m is not None:
        if m["histogram"] > 0:
            if alignment != "역배열":
                score += 1
                reasons.append("MACD 상방 (모멘텀 우위)")
            else:
                reasons.append("MACD 수렴 조짐 — 추세 전환 확인 전까지 미반영")
        else:
            if alignment != "정배열":
                score -= 1
                reasons.append("MACD 하방")
            else:
                reasons.append("MACD 조정 조짐 — 상승 추세 유지 중")
    if vol_surge is not None and vol_surge >= 1.5:
        reasons.append(f"거래량 급증 (60일 평균 대비 {vol_surge}배)")

    if alignment is None or r is None:
        verdict = "판단 보류"
        reasons.append("데이터 부족 (120일 이상 시세 필요)")
    elif score >= 2:
        verdict = "매수"
    elif score <= -2:
        verdict = "매도"
    else:
        verdict = "중립"

    return {"ma": ma, "ma_alignment": alignment, "rsi": r, "macd": m,
            "cross": cross, "volume_surge_ratio": vol_surge,
            "signal": {"verdict": verdict, "score": score, "reasons": reasons}}
