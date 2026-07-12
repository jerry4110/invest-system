"""T-26 수용 기준: 종합 판단(전략 반영·계좌정보 미포함), AI 토론 3호출, 딥리서치 4대 지침, 이력."""
import json

import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod


class CapturingLLM:
    """프롬프트를 기록하고 지정 응답을 돌려주는 가짜 어댑터."""
    model = "fake"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, prompt, max_tokens=1024):
        from backend.adapters.llm.base import LLMResult
        self.prompts.append(prompt)
        return LLMResult(text=self.responses.pop(0), model="fake",
                         input_tokens=100, output_tokens=100, cost_usd=0.001)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    from backend.services import analysis_service, strategy_service
    strategy_service.update_guideline("PER 15 이하 분할매수 원칙")
    monkeypatch.setattr(analysis_service, "_gather_context",
                        lambda t: {"summary_text": "[A] ROE 12% [B] 중립 [C] 호재 2건",
                                   "price": 285000, "name": "삼성전자"})
    return monkeypatch


JUDGMENT = json.dumps({
    "fair_value_current": 320000, "fair_value_future": 380000,
    "recommendation": "매수",
    "plan": "300,000원 이하에서 3회 분할 매수, 1차 30%",
    "assumptions": ["영업이익 연 10% 성장 가정", "PER 밴드 12~18배"],
    "rationale": "재무 양호, 수급 중립",
}, ensure_ascii=False)


def test_comprehensive_judgment(env):
    from backend.services import analysis_service
    llm = CapturingLLM([JUDGMENT])
    r = analysis_service.comprehensive("005930", adapter=llm)
    assert r["recommendation"] == "매수"
    assert r["fair_value_current"] == 320000
    assert r["assumptions"]                                    # FR-04-34 가정 명시
    assert "참고자료" in r["disclaimer"]                        # FR-04-36
    # 전략 컨텍스트 반영 + 계좌정보 미전송 (NFR-01)
    assert "PER 15 이하 분할매수 원칙" in llm.prompts[0]
    assert "계좌" not in llm.prompts[0]
    # 이력 저장 (FR-04-37)
    from backend.infra.schema import AnalysisResult
    with db_mod.get_session() as s:
        assert s.query(AnalysisResult).filter_by(ticker="005930", kind="comprehensive").count() == 1


def test_comprehensive_parse_failure_returns_narrative(env):
    from backend.services import analysis_service
    r = analysis_service.comprehensive("005930", adapter=CapturingLLM(["JSON 아님 — 서술형 답변"]))
    assert r["recommendation"] is None
    assert "서술형" in r["narrative"]                          # 원문 보존, 실패 숨기지 않음


def test_debate_bull_bear_conclusion(env):
    from backend.services import analysis_service
    llm = CapturingLLM(["[강세론] 성장 지속", "[약세론] 밸류 부담", "[결론] 분할 접근 권고"])
    r = analysis_service.debate("005930", adapter=llm)
    assert "성장 지속" in r["bull"] and "밸류 부담" in r["bear"]
    assert "분할 접근" in r["conclusion"]
    assert len(llm.prompts) == 3
    assert "밸류 부담" in llm.prompts[2]                        # 중재자가 양측 주장 수신


def test_deep_research_includes_4_directives(env):
    from backend.services import analysis_service
    llm = CapturingLLM(["딥리서치 결과"])
    analysis_service.deep_research("005930", adapter=llm)
    p = llm.prompts[0]
    for phrase in ("정보의 범위", "의사결정의 원칙", "관찰하는", "낙관"):
        assert phrase in p                                      # FR-04-43 4대 행동지침


def test_history_api(env):
    from backend.services import analysis_service
    analysis_service.comprehensive("005930", adapter=CapturingLLM([JUDGMENT]))
    client = TestClient(main_mod.create_app())
    body = client.get("/api/analysis/history/005930").json()
    assert len(body) == 1 and body[0]["kind"] == "comprehensive"
    assert body[0]["created_at"]
