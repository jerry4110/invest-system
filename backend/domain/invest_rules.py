"""투자유형 분류 규칙 (D-021 보완, 2026-07-14 사용자 지정).

분류는 저장값이 아니라 조회 시 이 규칙으로 계산되므로, 파일 재스캔·재적재와
무관하게 항상 동일하게 유지된다. 규칙 변경은 이 파일만 수정하면 된다.

우선순위: ① 종목명 오버라이드 → ② 해외투자 키워드 → ③ 기본(국내투자)
"""

# ETF 브랜드 (국내 상장 ETF/펀드 판별)
ETF_BRANDS = ("KODEX", "TIGER", "ACE", "SOL", "PLUS", "RISE", "KBSTAR", "HANARO",
              "ARIRANG", "KOSEF", "TIMEFOLIO", "TIME ", "KOACT", "KIWOOM",
              "히어로즈", "WOORI", "BNK")

# 해외투자 국내 ETF 판별 키워드 (종목명에 포함 시)
OVERSEAS_THEME_KEYWORDS = (
    "글로벌", "차이나", "미국", "금현물", "금채권",     # 2026-07-14 1차 지정
    "구리선물",                                         # KODEX 구리선물(H)
    "인도", "일본", "유럽", "베트남", "나스닥", "S&P",   # 동일 원칙 확장
)

# 종목명 강제 분류 (키워드보다 우선) — 예외 종목은 여기에 추가
INVEST_OVERRIDES: dict[str, str] = {
    "KODEX 2차전지산업": "국내투자 국내 ETF",
    "TIGER 코스닥글로벌": "국내투자 국내 ETF",   # '글로벌' 키워드 예외 — 국내 코스닥 지수 상품
    # 예) "KIWOOM K-반도체북미공급망": "국내투자 국내 ETF",  # '북미'는 키워드 미해당이라 불필요
}


def is_etf(name: str) -> bool:
    upper = name.upper()
    return any(b in upper for b in ETF_BRANDS) or "ETF" in upper


def classify_domestic_etf(name: str) -> str:
    """국내 상장 ETF의 투자 지역 분류."""
    if name.strip() in INVEST_OVERRIDES:
        return INVEST_OVERRIDES[name.strip()]
    if any(k.upper() in name.upper() for k in OVERSEAS_THEME_KEYWORDS):
        return "해외투자 국내 ETF"
    return "국내투자 국내 ETF"
