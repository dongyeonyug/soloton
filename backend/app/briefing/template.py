"""슬롯필 계층 — 코드가 모든 수치·등급·출처·시각을 소유(구조적 인용).

`build_slots` 는 RiskGrade.basis_values 를 FilledNumber 로 바인딩하되, 각 슬롯의 label 은
반드시 자신의 metric 에서 유래한다(AC4 attribution — 파고 자리에 풍속값 오결합 불가).
결측 슬롯은 '정보없음' 으로 자백한다. 이 계층의 산출물은 항상 정확하다.
"""

from __future__ import annotations

from datetime import datetime

from ..models import (
    Activity,
    BriefingSlots,
    FilledNumber,
    Grade,
    RiskGrade,
)
from ..spots import Spot

MISSING_TEXT = "정보없음"
EMERGENCY = "해양경찰 신고 122"  # 숫자를 코드가 소유(LLM 아님)


def build_slots(
    spot: Spot,
    risk: RiskGrade,
    snapshot_as_of: datetime | None,
) -> BriefingSlots:
    filled: list[FilledNumber] = []
    for bv in risk.basis_values:
        # label 은 basis_value(=metric 소유)에서만 온다 → 오결합 불가
        filled.append(
            FilledNumber(
                label=bv.label,
                value=bv.value,
                unit=bv.unit,
                source=bv.source,
                observed_at=bv.observed_at,
                is_missing=bv.is_missing,
            )
        )
    is_confession = risk.has_missing_critical or any(f.is_missing for f in filled)
    return BriefingSlots(
        spot_id=spot.id,
        time_slot=risk.time_slot,
        activity=risk.activity,
        grade=risk.grade,
        filled_numbers=filled,
        is_confession=is_confession,
        snapshot_as_of=snapshot_as_of,
    )


def _fmt_number(f: FilledNumber) -> str:
    if f.is_missing or f.value is None:
        return f"{f.label} {MISSING_TEXT}"
    # 정수형이면 소수점 제거
    val = f"{f.value:g}"
    return f"{f.label} {val}{f.unit}(출처: {f.source})"


def render_template(spot: Spot, risk: RiskGrade, slots: BriefingSlots) -> str:
    """코드 소유 근거 문장. 항상 정확한 구조적 인용."""
    parts = [_fmt_number(f) for f in slots.filled_numbers]
    metrics_line = ", ".join(parts)

    advisories = risk.basis_advisories
    if advisories:
        adv_line = ", ".join(a.kind.value for a in advisories)
    else:
        adv_line = "없음"

    as_of = (
        slots.snapshot_as_of.strftime("%Y-%m-%d %H:%M")
        if slots.snapshot_as_of
        else MISSING_TEXT
    )
    confession = " (일부 지표 정보없음 — 안전 판단 보수화)" if slots.is_confession else ""

    return (
        f"[{spot.name}] {risk.time_slot}시 {risk.activity.value} 기준 "
        f"위험도: {risk.grade.label_ko}{confession}. "
        f"{metrics_line}. 발효 특보: {adv_line}. 기준 시각 {as_of}."
    )


# 코드 소유 활동별 권고 (등급×활동). 결정론, LLM 아님.
_BASE_REC: dict[Grade, str] = {
    Grade.SAFE: "현재 지표는 안전 범위입니다. 기본 안전수칙을 지키세요.",
    Grade.CAUTION: "주의가 필요합니다. 기상 변화를 수시로 확인하세요.",
    Grade.DANGER: "위험합니다. 해당 활동을 자제하고 안전한 장소로 이동하세요.",
}
_ACTIVITY_REC: dict[tuple[Grade, Activity], str] = {
    (Grade.DANGER, Activity.ROCK_FISHING): "갯바위 고립·추락 위험이 큽니다. 진입하지 마세요.",
    (Grade.DANGER, Activity.SWIMMING): "입수 금지. 이안류·높은 파도에 주의하세요.",
    (Grade.CAUTION, Activity.SWIMMING): "어린이·노약자 입수를 자제하고 안전요원 지시를 따르세요.",
    (Grade.DANGER, Activity.FISHING): "소형선박 출항을 삼가세요.",
    (Grade.CAUTION, Activity.ROCK_FISHING): "구명조끼를 착용하고 파도 상황을 주시하세요.",
}


def build_recommendations(risk: RiskGrade, is_confession: bool) -> list[str]:
    recs = [_BASE_REC[risk.grade]]
    specific = _ACTIVITY_REC.get((risk.grade, risk.activity))
    if specific:
        recs.append(specific)
    if is_confession:
        recs.append("일부 관측값이 없어 실제 위험이 더 높을 수 있습니다.")
    if risk.grade is not Grade.SAFE:
        recs.append(f"위급 시 {EMERGENCY}.")
    return recs


def fallback_prose(spot: Spot, risk: RiskGrade, is_confession: bool) -> str:
    """LLM 미사용/가드 폴백용 숫자없는 산문(코드 생성, 항상 number-free)."""
    grade = risk.grade.label_ko
    activity = risk.activity.value
    base = {
        Grade.SAFE: f"{spot.name}의 현재 {activity} 여건은 대체로 안전한 편입니다. 기본 수칙을 지키며 즐기세요.",
        Grade.CAUTION: f"{spot.name}에서 {activity}을(를) 계획한다면 주의가 필요합니다. 기상 변화를 살피고 무리하지 마세요.",
        Grade.DANGER: f"{spot.name}의 현재 {activity} 여건은 위험합니다. 활동을 미루고 안전을 우선하세요.",
    }[risk.grade]
    if is_confession:
        base += " 일부 관측 정보가 없어 더 보수적으로 판단했습니다."
    return base
