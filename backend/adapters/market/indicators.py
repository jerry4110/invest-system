"""지표 레지스트리 (FR-02-11~12) — 코드 ↔ 벤더 심볼 매핑을 코드와 분리 관리.

주: KOSPI/KOSDAQ도 yfinance 심볼(^KS11/^KQ11) 사용 — pykrx는 KRX 계정 로그인이
필요해져(2026) Phase 2의 종목 수급·공매도 데이터 검토 시 재평가 (HANDOFF 참조).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorSpec:
    code: str      # 내부 코드
    name: str      # 표시명
    symbol: str    # yfinance 심볼
    category: str  # index | macro


INDICATORS: dict[str, IndicatorSpec] = {s.code: s for s in [
    IndicatorSpec("KOSPI",  "코스피",        "^KS11",   "index"),
    IndicatorSpec("KOSDAQ", "코스닥",        "^KQ11",   "index"),
    IndicatorSpec("NASDAQ", "나스닥",        "^IXIC",   "index"),
    IndicatorSpec("SP500",  "S&P 500",      "^GSPC",   "index"),
    IndicatorSpec("DOW",    "다우존스",      "^DJI",    "index"),
    IndicatorSpec("USDKRW", "원/달러 환율",  "KRW=X",   "macro"),
    IndicatorSpec("WTI",    "WTI 유가",     "CL=F",    "macro"),
    IndicatorSpec("GOLD",   "금 시세",      "GC=F",    "macro"),
    IndicatorSpec("BTC",    "비트코인",      "BTC-USD", "macro"),
    IndicatorSpec("UST10Y", "미국채 10년",   "^TNX",    "macro"),
]}
