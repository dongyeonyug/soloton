"""위험도 결정 — 순수함수. I/O·시계·난수 없음.

동일 입력 → 동일 등급(AC2). 등급은 기여 지표의 worst + 특보 override.
임계 지표(파고/풍속/특보) 결측 시 안전 불가 + CAUTION floor(AC5a).

신선도(`mark_stale`)도 순수함수로 유지한다 — 판정 기준시각 `as_of` 를 명시 인자로
받으므로 내부에서 시계를 읽지 않는다.
"""

from __future__ import annotations

from datetime import datetime

from ..models import (
    CRITICAL_METRICS,
    Advisory,
    AdvisoryKind,
    BasisValue,
    DataStatus,
    DecisionStep,
    Grade,
    MarineObservation,
    Metric,
    RiskGrade,
    RuleEvidence,
)
from .thresholds import (
    ADVISORY_MAX_AGE_SECONDS,
    ADVISORY_OVERRIDE,
    MAX_AGE_SECONDS,
    MISSING_CRITICAL_FLOOR,
    REFERENCE_METRICS,
    THRESHOLDS,
)

# 등급에 기여하는 수치 지표. 조류는 지역·활동별 검증 임계값 전까지 참고값이다.
CONTRIBUTING_METRICS: tuple[Metric, ...] = (
    Metric.WAVE_HEIGHT,
    Metric.WIND_SPEED,
)


def _worst(grades: list[Grade]) -> Grade:
    return max(grades, key=lambda g: g.rank) if grades else Grade.SAFE


def _escalate(current: Grade, floor: Grade) -> Grade:
    return current if current.rank >= floor.rank else floor


def _data_status(obs: MarineObservation | None, *, missing: bool) -> DataStatus:
    """관측값의 실제 상태를 API 계약으로 고정한다."""
    if missing:
        return DataStatus.STALE if obs is not None and obs.is_stale else DataStatus.MISSING
    if obs is not None and "실측" in obs.source:
        return DataStatus.OBSERVED
    if obs is not None and obs.source.startswith("Open-Meteo"):
        return DataStatus.FORECAST
    return DataStatus.AVAILABLE


def mark_stale(
    observations: dict[Metric, MarineObservation],
    advisory: Advisory,
    as_of: datetime,
) -> tuple[dict[Metric, MarineObservation], Advisory]:
    """신선도 만료 지표를 is_missing 으로 강등(순수, as_of 명시)."""
    out: dict[Metric, MarineObservation] = {}
    for metric, obs in observations.items():
        max_age = MAX_AGE_SECONDS.get(metric, 6 * 3600)
        if (
            not obs.is_missing
            and obs.observed_at is not None
            and (as_of - obs.observed_at).total_seconds() > max_age
        ):
            out[metric] = obs.model_copy(
                update={"is_missing": True, "is_stale": True, "value": None}
            )
        else:
            out[metric] = obs

    adv = advisory
    if (
        not adv.is_missing
        and adv.effective_at is not None
        and (as_of - adv.effective_at).total_seconds() > ADVISORY_MAX_AGE_SECONDS
    ):
        adv = adv.model_copy(update={"is_missing": True, "is_stale": True})
    return out, adv


def evaluate(
    observations: dict[Metric, MarineObservation],
    advisory: Advisory,
    time_slot: str,
) -> RiskGrade:
    """관측·특보 → 해안 활동 참고 등급. 순수·결정론."""
    basis_values: list[BasisValue] = []
    present_grades: list[Grade] = []
    decision_steps: list[DecisionStep] = []
    has_missing_critical = False

    for metric in CONTRIBUTING_METRICS:
        band = THRESHOLDS[metric]
        obs = observations.get(metric)
        is_critical = metric in CRITICAL_METRICS
        missing = obs is None or obs.is_missing or obs.value is None

        if missing:
            if is_critical:
                has_missing_critical = True
            basis_values.append(
                BasisValue(
                    label=band.label,
                    metric=metric,
                    value=None,
                    unit=band.unit,
                    checked_source=obs.source if obs else "",
                    criterion=band.source,
                    rule_evidence=band.evidence,
                    observed_at=obs.observed_at if obs else None,
                    is_missing=True,
                    missing_reason=obs.missing_reason if obs else None,
                    data_status=_data_status(obs, missing=True),
                    is_critical=is_critical,
                    # 결측 임계지표는 CAUTION floor 를 대표, 비임계는 기여 없음(SAFE)
                    contributed_grade=(
                        MISSING_CRITICAL_FLOOR if is_critical else Grade.SAFE
                    ),
                )
            )
            decision_steps.append(
                DecisionStep(
                    label=band.label,
                    detail=(
                        "값이 없어 안전 등급을 낼 수 없어 최소 주의로 보수 처리"
                        if is_critical
                        else "값이 없어 이 지표는 계산에 반영하지 않음"
                    ),
                    result_grade=MISSING_CRITICAL_FLOOR if is_critical else None,
                    rule_evidence=band.evidence,
                )
            )
        else:
            g = band.grade_for(obs.value)
            present_grades.append(g)
            basis_values.append(
                BasisValue(
                    label=band.label,
                    metric=metric,
                    value=obs.value,
                    unit=band.unit,
                    observed_source=obs.source,
                    checked_source=obs.source,
                    criterion=band.source,
                    rule_evidence=band.evidence,
                    observed_at=obs.observed_at,
                    is_missing=False,
                    data_status=_data_status(obs, missing=False),
                    is_critical=is_critical,
                    contributed_grade=g,
                )
            )
            decision_steps.append(
                DecisionStep(
                    label=band.label,
                    detail="값과 임계 밴드를 비교한 결과",
                    result_grade=g,
                    rule_evidence=band.evidence,
                )
            )

    # 참고 지표(조류·조위·수온) — 등급에 기여하지 않으나 근거로 인용한다.
    # 결측이어도 has_missing_critical 을 올리지 않는다(등급 비임계).
    for metric, (unit, label, reference_note) in REFERENCE_METRICS.items():
        obs = observations.get(metric)
        missing = obs is None or obs.is_missing or obs.value is None
        basis_values.append(
            BasisValue(
                label=label,
                metric=metric,
                value=None if missing else obs.value,
                unit=unit,
                # 결측이면 출처 주장 없음(관측된 적 없는 값에 실측 라벨 금지)
                observed_source="" if missing else obs.source,
                checked_source=obs.source if obs else "",
                observed_at=None if missing else obs.observed_at,
                is_missing=missing,
                missing_reason=obs.missing_reason if missing and obs else None,
                data_status=_data_status(obs, missing=missing),
                is_reference=True,
                reference_note=reference_note,
                reference_station_name=obs.reference_station_name if obs else None,
                reference_station_code=obs.reference_station_code if obs else None,
                reference_distance_km=obs.reference_distance_km if obs else None,
                contributed_grade=Grade.SAFE,
            )
        )
        if metric is Metric.CURRENT_SPEED:
            decision_steps.append(
                DecisionStep(
                    label=label,
                    detail=reference_note,
                    result_grade=None,
                )
            )

    grade = _worst(present_grades)

    # 특보 처리
    basis_advisories: list[Advisory] = []
    if advisory.is_missing:
        has_missing_critical = True
        decision_steps.append(
            DecisionStep(
                label="기상특보",
                detail="특보 정보를 확인하지 못해 안전 등급을 낼 수 없어 최소 주의로 보수 처리",
                result_grade=MISSING_CRITICAL_FLOOR,
            )
        )
    elif advisory.kind is not AdvisoryKind.NONE:
        override = ADVISORY_OVERRIDE.get(advisory.kind)
        if override is not None:
            grade = _escalate(grade, override[0])
            decision_steps.append(
                DecisionStep(
                    label="기상특보",
                    detail=f"{advisory.kind.value}가 최종 등급의 하한을 올림",
                    result_grade=override[0],
                    rule_evidence=RuleEvidence.OFFICIAL_BASELINE,
                )
            )
        basis_advisories.append(advisory)
    else:
        decision_steps.append(
            DecisionStep(label="기상특보", detail="활성 특보 없음", result_grade=None)
        )

    # 결측 임계지표 → 안전 불가, CAUTION floor
    if has_missing_critical:
        grade = _escalate(grade, MISSING_CRITICAL_FLOOR)

    decision_steps.append(
        DecisionStep(
            label="최종 위험도",
            detail="지표 중 가장 높은 등급, 특보 상향, 결측 보수 규칙을 모두 반영",
            result_grade=grade,
        )
    )

    return RiskGrade(
        grade=grade,
        time_slot=time_slot,
        basis_values=basis_values,
        basis_advisories=basis_advisories,
        advisory=advisory,
        decision_steps=decision_steps,
        has_missing_critical=has_missing_critical,
    )
