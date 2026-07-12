"""LLMAdapter 추상 인터페이스 (D-007·D-015, NFR-03).

구현체 교체 가능 구조 — 첫 구현체는 OpenAI (openai_adapter.py).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class LLMAdapter(ABC):
    model: str

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int = 1024) -> LLMResult: ...
