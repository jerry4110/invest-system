"""투자유형 분류 규칙 (2026-07-14 사용자 지정) — 재스캔과 무관하게 규칙으로 유지."""
import pytest

from backend.services.portfolio_service import _classify_invest


def _h(name, market="KRX"):
    return {"name": name, "market": market}

국내투자_국내ETF = [
    "KoAct 코스닥액티브",
    "KODEX 삼성전자채권혼합",
    "KODEX AI반도체TOP2플러스",
    "HANARO Fn K-반도체",
    "KODEX AI전력핵심설비",
    "SOL 반도체소부장",
    "TIGER 코스닥150IT",
    "KIWOOM K-반도체북미공급망",       # '북미'는 미국 키워드 아님
    "KODEX 2차전지산업",
    "TIGER 코스닥글로벌",   # 국내 코스닥 지수 상품 — 오버라이드 (2026-07-14)
]

해외투자_국내ETF = [
    "TIME 차이나AI테크액티브",
    "PLUS 글로벌휴머노이드로봇액티브",
    "TIME 글로벌우주테크&방산액티브",
    "TIGER KRX금현물",
    "PLUS 금채권혼합",
    "SOL 미국양자컴퓨팅TOP10",
    "PLUS 글로벌희토류전략자원기업MV",
    "RISE 미국반도체NYSE",
    "KODEX 구리선물(H)",
]


@pytest.mark.parametrize("name", 국내투자_국내ETF)
def test_domestic_invest_etf(name):
    assert _classify_invest(_h(name)) == "국내투자 국내 ETF", name


@pytest.mark.parametrize("name", 해외투자_국내ETF)
def test_overseas_invest_etf(name):
    assert _classify_invest(_h(name)) == "해외투자 국내 ETF", name


def test_individual_and_overseas_unchanged():
    assert _classify_invest(_h("삼성전자")) == "국내 개별주식"
    assert _classify_invest(_h("엔비디아", market="OVERSEAS")) == "해외 개별주식·ETF"
