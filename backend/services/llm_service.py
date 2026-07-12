"""LLM 호출 게이트웨이 (T-21) — 프롬프트 템플릿·월 비용 상한 가드·사용량 기록.

모든 LLM 호출은 guarded_complete를 경유한다 (직접 어댑터 호출 금지 — constitution §2.7).
"""
import logging
from datetime import datetime
from pathlib import Path

from backend.adapters.llm.base import LLMAdapter, LLMResult
from backend.infra.db import get_session
from backend.infra.schema import AppSetting, LlmUsage

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
DEFAULT_LIMIT_USD = 30.0  # D-015


class BudgetExceeded(Exception):
    """월 비용 상한 초과 — 분석 기능 일시 차단."""


def render_prompt(_template: str, **variables) -> str:
    """템플릿 로드·치환. 첫 인자명은 변수 키({name} 등)와 충돌하지 않도록 _template."""
    template = (PROMPT_DIR / f"{_template}.md").read_text(encoding="utf-8")
    return template.format(**variables)


def get_monthly_limit() -> float:
    with get_session() as s:
        row = s.get(AppSetting, "llm_monthly_limit_usd")
    return float(row.value) if row else DEFAULT_LIMIT_USD


def set_monthly_limit(limit_usd: float) -> None:
    with get_session() as s:
        s.merge(AppSetting(key="llm_monthly_limit_usd", value=str(limit_usd)))
        s.commit()


def _month_cost() -> tuple[float, int]:
    start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with get_session() as s:
        rows = s.query(LlmUsage).filter(LlmUsage.ts >= start).all()
    return sum(r.cost_usd for r in rows), len(rows)


def get_usage_summary() -> dict:
    cost, calls = _month_cost()
    limit = get_monthly_limit()
    return {"month_cost_usd": round(cost, 4), "limit_usd": limit,
            "remaining_usd": round(max(limit - cost, 0), 4), "calls": calls,
            "as_of": datetime.now().isoformat(timespec="seconds")}


def guarded_complete(prompt_name: str, adapter: LLMAdapter | None = None,
                     max_tokens: int = 1024, **variables) -> LLMResult:
    """상한 확인 → 호출 → 사용량 기록. 상한 초과 시 BudgetExceeded (D-015)."""
    cost, _ = _month_cost()
    limit = get_monthly_limit()
    if cost >= limit:
        raise BudgetExceeded(
            f"이번 달 LLM 비용(${cost:.2f})이 상한(${limit:.2f})에 도달했습니다 — "
            "설정에서 상한을 조정하거나 다음 달까지 기다려 주세요")

    if adapter is None:
        from backend.adapters.llm.openai_adapter import OpenAIAdapter
        adapter = OpenAIAdapter()

    prompt = render_prompt(prompt_name, **variables)
    result = adapter.complete(prompt, max_tokens=max_tokens)

    with get_session() as s:
        s.add(LlmUsage(ts=datetime.now(), model=result.model, prompt_name=prompt_name,
                       input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                       cost_usd=result.cost_usd))
        s.commit()
    logger.info("LLM 호출: %s (%s) $%.4f", prompt_name, result.model, result.cost_usd)
    return result
