"""브리핑 조립 — 슬롯필 + LLM 산문(가드 통과 시) + 폴백.

LLM 호출은 주입 가능(llm_fn)하여 테스트를 결정론적으로 유지한다. 가드(AC6)를 통과하지
못한 산문은 절대 서빙하지 않고 코드 생성 폴백 산문으로 대체한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from ..config import get_settings
from ..models import Briefing, ProseStatus, RiskGrade
from ..spots import Spot
from . import guard
from .prompt import SYSTEM_PROMPT, build_user_prompt
from .template import (
    build_recommendations,
    build_slots,
    fallback_prose,
    render_template,
)

# llm_fn(system, user) -> str
LLMFn = Callable[[str, str], str]


def _default_llm(*, timeout_seconds: float | None = None) -> LLMFn | None:
    settings = get_settings()
    if not settings.has_llm:
        return None

    def call(system: str, user: str) -> str:
        import anthropic

        client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=timeout_seconds,
        )
        msg = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in msg.content if getattr(block, "type", None) == "text"
        )

    return call


def generate_briefing(
    spot: Spot,
    risk: RiskGrade,
    snapshot_as_of: datetime | None,
    *,
    llm_fn: LLMFn | None = None,
    baked_prose: str | None = None,
    fallback_status: ProseStatus = ProseStatus.DETERMINISTIC_FALLBACK,
    safe_window=None,
    safe_window_assessment=None,
) -> Briefing:
    slots = build_slots(spot, risk, snapshot_as_of)
    template_text = render_template(spot, risk, slots)
    recommendations = build_recommendations(risk, slots.is_confession)

    prose = ""
    prose_status = fallback_status
    if baked_prose is not None:
        # 크론 프리-베이크 산문. 저장분이라도 런타임 가드를 재통과해야만 서빙(이중 게이트).
        # 통과 못 하면 prose 는 빈 채로 두어 아래 폴백으로 흐른다.
        if baked_prose and guard.is_number_free(baked_prose):
            prose = baked_prose.strip()
            prose_status = ProseStatus.VERIFIED
        elif baked_prose:
            prose_status = ProseStatus.BLOCKED_BY_GUARD
    else:
        fn = llm_fn if llm_fn is not None else _default_llm()
        if fn is not None:
            try:
                candidate = fn(SYSTEM_PROMPT, build_user_prompt(spot, risk))
            except Exception:
                candidate = ""
            # 런타임 가드: 무허용 숫자 발견 → 산문 폐기(AC6)
            if candidate and guard.is_number_free(candidate):
                prose = candidate.strip()
                prose_status = ProseStatus.VERIFIED
            elif candidate:
                prose_status = ProseStatus.BLOCKED_BY_GUARD
            else:
                prose_status = ProseStatus.GENERATION_UNAVAILABLE
        else:
            prose_status = ProseStatus.GENERATION_UNAVAILABLE

    if not prose:
        prose = fallback_prose(spot, risk, slots.is_confession)

    return Briefing(
        spot_id=spot.id,
        time_slot=risk.time_slot,
        grade=risk.grade,
        template_text=template_text,
        llm_prose=prose,
        citations=slots.filled_numbers,
        recommendations=recommendations,
        is_confession=slots.is_confession,
        has_missing_critical=risk.has_missing_critical,
        advisory=risk.advisory,
        decision_steps=risk.decision_steps,
        prose_status=prose_status,
        snapshot_as_of=snapshot_as_of,
        safe_window=safe_window,
        safe_window_assessment=safe_window_assessment,
    )
