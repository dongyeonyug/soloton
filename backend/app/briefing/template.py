"""슬롯필 계층 — 코드가 모든 수치·등급·출처·시각을 소유(구조적 인용).

`build_slots` 는 RiskGrade.basis_values 를 FilledNumber 로 바인딩하되, 각 슬롯의 label 은
반드시 자신의 metric 에서 유래한다(AC4 attribution — 파고 자리에 풍속값 오결합 불가).
결측 슬롯은 '정보없음' 으로 자백한다. 이 계층의 산출물은 항상 정확하다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from ..models import (
    BriefingSlots,
    FilledNumber,
    Grade,
    RiskGrade,
)
from ..spots import Spot

MISSING_TEXT = "정보없음"
EMERGENCY = "해양경찰 신고 122"  # 숫자를 코드가 소유(LLM 아님)
KST = ZoneInfo("Asia/Seoul")


def observed_kind(observed_source: str) -> str:
    """관측 출처 라벨 → UI 배지 분류. 라벨은 코드 소유 상수(resolver/openmeteo)뿐이다."""
    if "실측" in observed_source:
        return "실측"
    if observed_source.startswith("Open-Meteo"):
        return "예보"
    return ""


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
                observed_source=bv.observed_source,
                checked_source=bv.checked_source,
                observed_kind=observed_kind(bv.observed_source),
                criterion=bv.criterion,
                rule_evidence=bv.rule_evidence,
                observed_at=bv.observed_at,
                is_missing=bv.is_missing,
                missing_reason=bv.missing_reason,
                data_status=bv.data_status,
                is_critical=bv.is_critical,
                is_reference=bv.is_reference,
                reference_note=bv.reference_note,
                reference_station_name=bv.reference_station_name,
                reference_station_code=bv.reference_station_code,
                reference_distance_km=bv.reference_distance_km,
            )
        )
    # 참고 지표(등급 비반영) 결측은 자백 트리거가 아니다 — 보수화 문구는 임계 지표 몫.
    is_confession = risk.has_missing_critical or any(
        f.is_missing for f in filled if not f.is_reference
    )
    return BriefingSlots(
        spot_id=spot.id,
        time_slot=risk.time_slot,
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
    src = f.observed_source or MISSING_TEXT
    if f.is_reference:
        reference = ""
        if f.reference_station_name:
            reference = f", 참고 관측소: {f.reference_station_name}"
            if f.reference_distance_km is not None:
                reference += f"(약 {f.reference_distance_km:g}km)"
        return f"{f.label} {val}{f.unit}(출처: {src}{reference}, 등급 비반영 참고값)"
    return f"{f.label} {val}{f.unit}(출처: {src} / 판단 기준: {f.criterion})"


def _fmt_kst(dt: datetime | None) -> str:
    """사용자 표시용 기준 시각. 스냅샷 저장값은 UTC naive 이므로 KST로 변환한다."""
    if dt is None:
        return MISSING_TEXT
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")


def render_template(spot: Spot, risk: RiskGrade, slots: BriefingSlots) -> str:
    """코드 소유 근거 문장. 항상 정확한 구조적 인용."""
    parts = [_fmt_number(f) for f in slots.filled_numbers]
    metrics_line = ", ".join(parts)

    advisories = risk.basis_advisories
    if advisories:
        adv_line = ", ".join(a.kind.value for a in advisories)
    else:
        adv_line = "없음"

    as_of = _fmt_kst(slots.snapshot_as_of)
    confession = " (일부 지표 정보없음 — 안전 판단 보수화)" if slots.is_confession else ""

    return (
        f"[{spot.name}] {risk.time_slot}시 해안 활동 참고 기준 "
        f"위험도: {risk.grade.label_ko}{confession}. "
        f"{metrics_line}. 발효 특보: {adv_line}. 기준 시각 {as_of}."
    )


# 코드 소유 등급별 권고. 결정론, LLM 아님.
_BASE_REC: dict[Grade, str] = {
    Grade.SAFE: "현재 지표는 참고 범위 안입니다. 현장 안내와 기본 안전수칙을 확인하세요.",
    Grade.CAUTION: "주의가 필요합니다. 기상 변화를 수시로 확인하세요.",
    Grade.DANGER: "위험 신호가 확인됩니다. 해안 활동을 미루고 현장 안전 안내를 따르세요.",
}


def build_recommendations(risk: RiskGrade, is_confession: bool) -> list[str]:
    recs = [_BASE_REC[risk.grade]]
    if is_confession:
        recs.append("일부 관측값이 없어 실제 위험이 더 높을 수 있습니다.")
    if risk.grade is not Grade.SAFE:
        recs.append(f"위급 시 {EMERGENCY}.")
    return recs


def fallback_prose(spot: Spot, risk: RiskGrade, is_confession: bool) -> str:
    """LLM 미사용/가드 폴백용 숫자없는 산문(코드 생성, 항상 number-free)."""
    base = {
        Grade.SAFE: f"{spot.name}의 현재 해안 여건은 참고 범위 안입니다. 현장 안내와 기본 수칙을 확인하세요.",
        Grade.CAUTION: f"{spot.name}의 해안 여건은 주의가 필요합니다. 기상 변화를 살피고 무리하지 마세요.",
        Grade.DANGER: f"{spot.name}의 현재 해안 여건은 위험 신호가 있습니다. 활동을 미루고 안전을 우선하세요.",
    }[risk.grade]
    if is_confession:
        base += " 일부 관측 정보가 없어 더 보수적으로 판단했습니다."
    return base
