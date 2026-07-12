"""T-21 수용 기준: 프롬프트 템플릿, 비용 기록, 월 상한 가드, 사용량 API."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    return db_mod.get_session


class FakeAdapter:
    """OpenAI 대체 — 호출당 $0.02 비용의 가짜 응답."""
    model = "fake-model"

    def complete(self, prompt: str, max_tokens: int = 1024):
        from backend.adapters.llm.base import LLMResult
        return LLMResult(text=f"응답: {prompt[:20]}", model=self.model,
                         input_tokens=100, output_tokens=50, cost_usd=0.02)


def test_prompt_template_render():
    """프롬프트는 backend/prompts/*.md 파일로 코드와 분리 (PRD_Phase2 §3)."""
    from backend.services.llm_service import render_prompt
    text = render_prompt("qualitative_factors", ticker="005930", name="삼성전자",
                         context="[재무 요약]", strategy="[전략]")
    assert "005930" in text and "삼성전자" in text
    assert "{ticker}" not in text                    # 미치환 변수 없음
    assert "투자 참고" in text or "참고자료" in text  # 고지 유도 (FR-04-36)


def test_guarded_complete_records_usage(fresh):
    from backend.infra.schema import LlmUsage
    from backend.services import llm_service

    r = llm_service.guarded_complete("qualitative_factors", adapter=FakeAdapter(),
                                     ticker="005930", name="삼성전자",
                                     context="c", strategy="s")
    assert r.text.startswith("응답:")
    with fresh() as s:
        row = s.query(LlmUsage).one()
        assert row.cost_usd == 0.02 and row.prompt_name == "qualitative_factors"
        assert row.model == "fake-model"


def test_budget_guard_blocks_over_limit(fresh):
    from backend.services import llm_service
    from backend.services.llm_service import BudgetExceeded

    llm_service.set_monthly_limit(0.03)
    kw = dict(adapter=FakeAdapter(), ticker="t", name="n", context="c", strategy="s")
    llm_service.guarded_complete("qualitative_factors", **kw)   # 누계 0.02 < 0.03
    with pytest.raises(BudgetExceeded, match="상한"):
        llm_service.guarded_complete("qualitative_factors", **kw)  # 0.02 >= 0.03 차단


def test_usage_summary_current_month_only(fresh):
    from backend.infra.schema import LlmUsage
    from backend.services import llm_service

    with fresh() as s:
        s.add(LlmUsage(ts=datetime(2020, 1, 1), model="old", prompt_name="x",
                       input_tokens=1, output_tokens=1, cost_usd=99.0))
        s.commit()
    llm_service.guarded_complete("qualitative_factors", adapter=FakeAdapter(),
                                 ticker="t", name="n", context="c", strategy="s")
    summary = llm_service.get_usage_summary()
    assert summary["month_cost_usd"] == 0.02        # 과거 달 제외
    assert summary["limit_usd"] == 30.0              # 기본값 (D-015)
    assert summary["calls"] == 1


def test_usage_api_and_limit_setting(fresh):
    from backend.services import llm_service
    client = TestClient(main_mod.create_app())
    body = client.get("/api/settings/llm-usage").json()
    assert body["limit_usd"] == 30.0 and "month_cost_usd" in body
    r = client.put("/api/settings/llm-limit", json={"limit_usd": 50})
    assert r.status_code == 200
    assert client.get("/api/settings/llm-usage").json()["limit_usd"] == 50.0
    assert client.put("/api/settings/llm-limit", json={"limit_usd": -5}).status_code == 422


def test_openai_cost_table():
    """모델별 단가 계산 (실호출 없음)."""
    from backend.adapters.llm.openai_adapter import calc_cost
    # gpt-4o-mini: $0.15/1M input, $0.60/1M output
    assert calc_cost("gpt-4o-mini", 1_000_000, 0) == pytest.approx(0.15)
    assert calc_cost("gpt-4o-mini", 0, 1_000_000) == pytest.approx(0.60)
    assert calc_cost("unknown-model", 1000, 1000) > 0   # 미등록 모델은 보수적 단가
