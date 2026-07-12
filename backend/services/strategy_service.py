"""투자전략 서비스 (F-01) — 페르소나·지침 버전·문서·목표배분."""
from datetime import datetime

from backend.infra.db import get_session
from backend.infra.schema import Strategy, StrategyFile, TargetAllocation

PERSONAS = ("value", "growth", "trader")

# FR-01-03: 페르소나별 기본 행동양식 템플릿 (수정 가능)
TEMPLATES = {
    "value": """[가치투자자 기본 행동양식]
- 내재가치 대비 저평가된 기업만 매수한다 (안전마진 30% 이상).
- PER·PBR·ROE·FCF 기반으로 판단하고, 시장의 단기 변동에 반응하지 않는다.
- 매수 전 사업보고서·재무제표 3개년을 반드시 확인한다.
- 보유 기간은 최소 1년 이상을 원칙으로 하고, 펀더멘털 훼손 시에만 매도한다.
- 한 종목 비중은 총자산의 20%를 넘기지 않는다.""",
    "growth": """[성장주 투자자 기본 행동양식]
- 매출·EPS가 연 15% 이상 성장하는 기업에 집중한다 (기능요건정의서 Tier 1 기준 참조).
- 산업의 TAM이 확장 중인지, 시장지배력이 강화되는지 확인한다.
- 밸류에이션은 PEG 1.5 이하를 선호하되 성장의 질을 우선한다.
- 성장 스토리가 꺾이면(2분기 연속 성장률 둔화) 손실 여부와 무관하게 재검토한다.
- 변동성을 감내하되 한 종목 비중 25% 초과 금지.""",
    "trader": """[단기 트레이더 기본 행동양식]
- 추세와 수급(거래량·외국인/기관 동향)을 우선 판단 기준으로 삼는다.
- 진입 전 손절가(-5~7%)와 목표가를 반드시 정하고 기록한다.
- Donchian 채널·이동평균선 돌파 등 정의된 시그널로만 진입한다.
- 손절은 기계적으로 실행한다 — 예외 없음.
- 하루 최대 신규 진입 2종목, 단일 포지션 위험은 총자산의 2% 이내.""",
}


def _get_or_create(persona: str = "value") -> Strategy:
    with get_session() as s:
        row = s.query(Strategy).order_by(Strategy.id.desc()).first()
        if row is None:
            row = Strategy(persona=persona, guideline_text=TEMPLATES[persona], version=1)
            s.add(row)
            s.commit()
        return row


def get_strategy() -> dict:
    st = _get_or_create()
    with get_session() as s:
        files = s.query(StrategyFile).filter_by(strategy_id=st.id).all()
        alloc = {r.key: r.value_pct for r in s.query(TargetAllocation).all()}
    return {
        "persona": st.persona, "guideline_text": st.guideline_text,
        "version": st.version, "updated_at": st.updated_at.isoformat(timespec="seconds"),
        "files": [{"id": f.id, "filename": f.filename,
                   "uploaded_at": f.uploaded_at.isoformat(timespec="seconds")} for f in files],
        "allocation": alloc,
    }


def set_persona(persona: str) -> None:
    """FR-01-01~02: 페르소나 전환 — 지침이 템플릿 그대로면 새 페르소나 템플릿 로드."""
    st = _get_or_create()
    with get_session() as s:
        row = s.get(Strategy, st.id)
        was_template = row.guideline_text.strip() in {t.strip() for t in TEMPLATES.values()}
        row.persona = persona
        if was_template:
            row.guideline_text = TEMPLATES[persona]
        row.updated_at = datetime.now()
        s.commit()


def update_guideline(text: str) -> int:
    """FR-01-11·14: 지침 수정 + 버전 증가."""
    st = _get_or_create()
    with get_session() as s:
        row = s.get(Strategy, st.id)
        row.guideline_text = text
        row.version += 1
        row.updated_at = datetime.now()
        s.commit()
        return row.version


def add_file(filename: str, parsed_text: str) -> None:
    st = _get_or_create()
    with get_session() as s:
        s.add(StrategyFile(strategy_id=st.id, filename=filename, parsed_text=parsed_text))
        s.commit()


def get_llm_context() -> str:
    """FR-01-13: LLM 분석용 전략 컨텍스트 (계좌 식별정보 미포함 — NFR-01)."""
    d = get_strategy()
    persona_kr = {"value": "가치투자자", "growth": "성장주 투자자", "trader": "단기 트레이더"}
    parts = [f"[투자 페르소나] {persona_kr[d['persona']]}",
             f"[투자 지침 v{d['version']}]\n{d['guideline_text']}"]
    with get_session() as s:
        for f in s.query(StrategyFile).all():
            parts.append(f"[업로드 지침: {f.filename}]\n{f.parsed_text}")
    if d["allocation"]:
        parts.append("[목표 자산배분] " + ", ".join(f"{k}={v}%" for k, v in d["allocation"].items()))
    return "\n\n".join(parts)


def set_allocation(alloc: dict[str, float]) -> None:
    """FR-01-15."""
    with get_session() as s:
        for k, v in alloc.items():
            row = s.query(TargetAllocation).filter_by(key=k).first()
            if row:
                row.value_pct = v
            else:
                s.add(TargetAllocation(key=k, value_pct=v))
        s.commit()
