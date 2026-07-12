"""OpenAI 구현체 (D-007). API 키는 secret_store의 openai_api_key (T-02 암호화 저장)."""
import logging

from backend.adapters.llm.base import LLMAdapter, LLMResult

logger = logging.getLogger(__name__)

# 모델별 단가 ($ / 1M tokens) — 2026-07 기준, 변경 시 이 표만 갱신
PRICING = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
}
_FALLBACK = (5.00, 15.00)  # 미등록 모델은 보수적(비싼) 단가로 가드

DEFAULT_MODEL = "gpt-4o-mini"


def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p_in, p_out = PRICING.get(model, _FALLBACK)
    return input_tokens / 1_000_000 * p_in + output_tokens / 1_000_000 * p_out


class OpenAIAdapter(LLMAdapter):
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def _client(self):
        from openai import OpenAI

        from backend.services.settings_service import get_secret
        key = get_secret("openai_api_key")
        if not key:
            raise RuntimeError("OpenAI API 키가 없습니다 — 설정 > API 키에 openai_api_key를 등록하세요")
        return OpenAI(api_key=key)

    def complete(self, prompt: str, max_tokens: int = 1024) -> LLMResult:
        res = self._client().chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        usage = res.usage
        return LLMResult(
            text=res.choices[0].message.content or "",
            model=self.model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            cost_usd=calc_cost(self.model, usage.prompt_tokens, usage.completion_tokens),
        )
