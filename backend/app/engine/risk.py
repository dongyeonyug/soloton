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
    Activity,
    Advisory,
    AdvisoryKind,
    BasisValue,
    Grade,
    MarineObservation,
    Metric,
    RiskGrade,
)
from .thresholds import (
    ADVISORY_MAX_AGE_SECONDS,
    ADVISORY_OVERRIDE,
    MAX_AGE_SECONDS,
    MISSING_CRITICAL_FLOOR,
    REFERENCE_METRICS,
    THRESHOLDS,
    effective_wave_band,
)

# 등급에 기여하는 지표(참고 지표 제외)
CONTRIBUTING_METRICS: tuple[Metric, ...] = (
    Metric.WAVE_HEIGHT,
    Metric.WIND_SPEED,
    Metric.CURRENT_SPEED,
)


def _worst(grades: list[Grade]) -> Grade:
    return max(grades, key=lambda g: g.rank) if grades else Grade.SAFE


def _escalate(current: Grade, floor: Grade) -> Grade:
    return current if current.rank >= floor.rank else floor


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
            out[metric] = obs.model_copy(update={"is_missing": True, "value": None})
        else:
            out[metric] = obs

    adv = advisory
    if (
        not adv.is_missing
        and adv.effective_at is not None
        and (as_of - adv.effective_at).total_seconds() > ADVISORY_MAX_AGE_SECONDS
    ):
        adv = adv.model_copy(update={"is_missing": True})
    return out, adv


def evaluate(
    observations: dict[Metric, MarineObservation],
    advisory: Advisory,
    activity: Activity,
    time_slot: str,
) -> RiskGrade:
    """관측·특보·활동 → 확정 등급. 순수·결정론."""
    basis_values: list[BasisValue] = []
    present_grades: list[Grade] = []
    has_missing_critical = False

    for metric in CONTRIBUTING_METRICS:
        band = (
            effective_wave_band(activity)
            if metric is Metric.WAVE_HEIGHT
            else THRESHOLDS[metric]
        )
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
                    criterion=band.source,
                    observed_at=obs.observed_at if obs else None,
                    is_missing=True,
                    # 결측 임계지표는 CAUTION floor 를 대표, 비임계는 기여 없음(SAFE)
                    contributed_grade=(
                        MISSING_CRITICAL_FLOOR if is_critical else Grade.SAFE
                    ),
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
                    criterion=band.source,
                    observed_at=obs.observed_at,
                    is_missing=False,
                    contributed_grade=g,
                )
            )

    # 참고 지표(조위·수온) — 등급에 기여하지 않으나 근거로 인용·결측 자백(is_reference).
    # 결측이어도 has_missing_critical 을 올리지 않는다(등급 비임계).
    for metric, (unit, label) in REFERENCE_METRICS.items():
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
                observed_at=None if missing else obs.observed_at,
                is_missing=missing,
                is_reference=True,
                contributed_grade=Grade.SAFE,
            )
        )

    grade = _worst(present_grades)

    # 특보 처리
    basis_advisories: list[Advisory] = []
    if advisory.is_missing:
        has_missing_critical = True
    elif advisory.kind is not AdvisoryKind.NONE:
        override = ADVISORY_OVERRIDE.get(advisory.kind)
        if override is not None:
            grade = _escalate(grade, override[0])
        basis_advisories.append(advisory)

    # 결측 임계지표 → 안전 불가, CAUTION floor
    if has_missing_critical:
        grade = _escalate(grade, MISSING_CRITICAL_FLOOR)

    return RiskGrade(
        grade=grade,
        time_slot=time_slot,
        activity=activity,
        basis_values=basis_values,
        basis_advisories=basis_advisories,
        has_missing_critical=has_missing_critical,
    )
