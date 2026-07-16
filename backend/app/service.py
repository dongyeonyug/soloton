"""파이프라인 조립 — 스냅샷 → 신선도 → 등급 → 브리핑. 라우터·테스트 공용.

C1 해소: 커밋 스냅샷 경로에서는 신선도 만료를 snapshot_as_of 기준으로 판정한다
(데모가 전부 '정보없음'으로 무너지지 않도록).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from .briefing.generate import LLMFn, generate_briefing
from .engine.forecast import assess_forecast_window, grade_point
from .engine.risk import evaluate, mark_stale
from .engine.thresholds import THRESHOLDS
from .ingest.cache import SnapshotDoc, get_snapshot
from .models import (
    Briefing,
    CurrentAdvisory,
    DataStatus,
    FilledNumber,
    ForecastConditions,
    ForecastCollectionStatus,
    ForecastPoint,
    Grade,
    Metric,
    PlanBriefing,
    PlanCoverageState,
    PlanDataState,
    PlanIntent,
    PlanOptions,
    ProseStatus,
    RiskGrade,
    SafeWindow,
    SafeWindowAssessment,
    SafeWindowStatus,
)
from .official_links import links_for
from .spots import Spot, get_spot

DEFAULT_TIME_SLOT = "현재"
# 예보 시계열 시각은 KST(Open-Meteo Asia/Seoul). '미래' 판정은 KST now 기준.
_KST = ZoneInfo("Asia/Seoul")
_FORECAST_MAX_AGE = timedelta(hours=6)
_ADVISORY_MAX_AGE = timedelta(hours=3)


def safe_window_for(
    spot: Spot,
    *,
    doc: SnapshotDoc | None = None,
    now: datetime | None = None,
) -> SafeWindow | None:
    """호환용 선택 결과. 계산 불가 원인은 safe_window_assessment_for가 소유한다."""
    return safe_window_assessment_for(spot, doc=doc, now=now).safe_window


def safe_window_assessment_for(
    spot: Spot,
    *,
    doc: SnapshotDoc | None = None,
    now: datetime | None = None,
) -> SafeWindowAssessment:
    """예보 수집 상태와 시간대 계산 결과를 한 계약으로 반환한다."""
    doc = doc or get_snapshot()
    snap = doc.spot(spot.id)
    if snap is None or not snap.forecast:
        collection_status = (
            snap.forecast_status
            if snap is not None
            else ForecastCollectionStatus.LEGACY_UNKNOWN
        )
        status_label = {
            ForecastCollectionStatus.EMPTY_RESPONSE: "시간별 예보 응답에 값이 없어",
            ForecastCollectionStatus.SOURCE_TIMEOUT: "정해진 수집 시간 안에 시간별 예보 응답이 없어",
            ForecastCollectionStatus.SOURCE_UNAVAILABLE: "시간별 예보 소스에 연결하지 못해",
            ForecastCollectionStatus.LEGACY_UNKNOWN: "이전 스냅샷에 시간별 예보 수집 기록이 없어",
        }.get(collection_status, "시간별 예보를 확인하지 못해")
        return SafeWindowAssessment(
            status=SafeWindowStatus.FORECAST_UNAVAILABLE,
            detail=f"{status_label} 활동 종료 참고 시각을 계산하지 않았습니다.",
            forecast_collected_at=snap.forecast_collected_at if snap is not None else None,
        )
    ref = now or datetime.now(_KST).replace(tzinfo=None)
    assessment = assess_forecast_window(snap.forecast, now=ref)
    return assessment.model_copy(
        update={"forecast_collected_at": snap.forecast_collected_at}
    )


def evaluate_spot(
    spot: Spot,
    *,
    doc: SnapshotDoc | None = None,
    time_slot: str = DEFAULT_TIME_SLOT,
) -> tuple[RiskGrade, datetime]:
    doc = doc or get_snapshot()
    snap = doc.spot(spot.id)
    if snap is None:
        raise KeyError(spot.id)
    as_of = doc.snapshot_as_of
    obs, adv = mark_stale(snap.as_map(), snap.advisory, as_of=as_of)
    risk = evaluate(obs, adv, time_slot)
    return risk, as_of


def brief_spot(
    spot: Spot,
    *,
    doc: SnapshotDoc | None = None,
    time_slot: str = DEFAULT_TIME_SLOT,
    llm_fn: LLMFn | None = None,
) -> Briefing:
    doc = doc or get_snapshot()
    risk, as_of = evaluate_spot(spot, doc=doc, time_slot=time_slot)

    # 공개 브리핑은 저장 산문이 없을 때도 코드 폴백만 사용한다. 주입 LLM은 가드 시연·테스트용이다.
    baked_prose: str | None = None if llm_fn is not None else ""
    fallback_status = ProseStatus.DETERMINISTIC_FALLBACK
    if (
        llm_fn is None
        and time_slot == DEFAULT_TIME_SLOT
        and doc.has_current_prose_contract
    ):
        snap = doc.spot(spot.id)
        if snap is not None:
            fallback_status = snap.prose_status
            # 산문과 상태가 함께 검증 계약이다. 상태가 verified 가 아니면 내용이 남아
            # 있어도 재사용하지 않는다. 빈 verified 는 손상된 스냅샷으로 보고 폴백한다.
            if (
                snap.prose_status == ProseStatus.VERIFIED
                and snap.llm_prose
            ):
                baked_prose = snap.llm_prose
            elif snap.prose_status == ProseStatus.VERIFIED:
                fallback_status = ProseStatus.DETERMINISTIC_FALLBACK

    safe_window_assessment = safe_window_assessment_for(spot, doc=doc)
    return generate_briefing(
        spot,
        risk,
        as_of,
        llm_fn=llm_fn,
        baked_prose=baked_prose,
        fallback_status=fallback_status,
        safe_window=safe_window_assessment.safe_window,
        safe_window_assessment=safe_window_assessment,
    )


def _kst_wall_time(value: datetime) -> datetime:
    """API의 +09:00 시각을 예보 시계열의 KST naive 벽시계값으로 바꾼다."""
    if value.tzinfo is None:
        return value
    return value.astimezone(_KST).replace(tzinfo=None)


def _utc_instant(value: datetime) -> datetime:
    """스냅샷 수집 시각(UTC naive)과 현재 시각을 같은 instant로 비교한다."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_stale(value: datetime | None, *, now: datetime, max_age: timedelta) -> bool:
    """수집 시각이 없거나 허용 나이를 넘으면 새 사실로 쓰지 않는다."""
    if value is None:
        return True
    return _utc_instant(now) - _utc_instant(value) > max_age


def _forecast_citations(point: ForecastPoint) -> list[FilledNumber]:
    """선택 예보점의 파고·풍속을 코드 소유 근거 슬롯으로 변환한다."""
    values = {
        Metric.WAVE_HEIGHT: point.wave_height,
        Metric.WIND_SPEED: point.wind_speed,
    }
    citations: list[FilledNumber] = []
    for metric in (Metric.WAVE_HEIGHT, Metric.WIND_SPEED):
        band = THRESHOLDS[metric]
        value = values[metric]
        missing = value is None
        citations.append(
            FilledNumber(
                label=band.label,
                value=value,
                unit=band.unit,
                observed_source="Open-Meteo 시간별 예보(수치모델)" if not missing else "",
                checked_source="Open-Meteo 시간별 예보(수치모델)",
                observed_kind="예보" if not missing else "",
                criterion=band.source,
                rule_evidence=band.evidence,
                observed_at=point.time,
                is_missing=missing,
                data_status=DataStatus.MISSING if missing else DataStatus.FORECAST,
                is_critical=True,
            )
        )
    return citations


def _coverage_for(data_state: PlanDataState) -> PlanCoverageState:
    """Phase 1은 water_play만 지원하므로 ready만 detailed로 표시한다."""
    return {
        PlanDataState.READY: PlanCoverageState.DETAILED,
        PlanDataState.PARTIAL: PlanCoverageState.PARTIAL,
        PlanDataState.STALE: PlanCoverageState.STALE,
        PlanDataState.UNAVAILABLE: PlanCoverageState.UNAVAILABLE,
        PlanDataState.INVALID_TIME: PlanCoverageState.INVALID_TIME,
    }[data_state]


def _plan_action(data_state: PlanDataState, grade: Grade | None) -> str:
    """허가·보장 표현 없이 다음 행동만 결정론적으로 안내한다."""
    if data_state is PlanDataState.INVALID_TIME:
        return "선택한 예보 시각이 갱신됐습니다. 실제 예보 시각을 다시 선택하세요."
    if data_state is PlanDataState.UNAVAILABLE:
        return (
            "시간별 예보를 확인하지 못했습니다. "
            "공식 해양기상 정보와 현장 안내를 확인하세요."
        )
    if data_state is PlanDataState.STALE:
        return (
            "기준 시각이 오래됐습니다. "
            "출발 전에 최신 특보와 현장 안내를 다시 확인하세요."
        )
    if data_state is PlanDataState.PARTIAL:
        return (
            "일부 핵심 예보 또는 특보 정보가 없습니다. "
            "안전하다고 단정하지 말고 공식 정보를 확인하세요."
        )
    return {
        Grade.SAFE: (
            "선택 시각의 예보는 참고 범위입니다. "
            "출발 전에 현재 특보와 현장 안내를 다시 확인하세요."
        ),
        Grade.CAUTION: (
            "선택 시각의 예보에 주의 신호가 있습니다. "
            "활동을 줄이거나 미루고 현장 안내를 확인하세요."
        ),
        Grade.DANGER: (
            "선택 시각의 예보에 위험 신호가 있습니다. "
            "물놀이를 미루고 현장 안전 안내를 따르세요."
        ),
    }[grade or Grade.CAUTION]


def build_plan_briefing(
    spot: Spot,
    intent: PlanIntent,
    *,
    doc: SnapshotDoc | None = None,
    now: datetime | None = None,
) -> PlanBriefing:
    """Phase 1 물놀이 계획을 LLM 없이 조립한다.

    선택 시각의 예보 등급과 현재 특보를 의도적으로 다른 객체에 둔다. 현재 특보는
    선택 시각의 미래 상태를 의미하지 않으므로 예보 등급을 올리거나 내리지 않는다.
    """
    if intent.spot_id != spot.id:
        raise ValueError("PlanIntent spot_id must match spot.id")

    doc = doc or get_snapshot()
    snap = doc.spot(spot.id)
    if snap is None:
        raise KeyError(spot.id)

    reference_now = now or datetime.now(_KST)
    requested_wall_time = _kst_wall_time(intent.requested_at)
    now_wall_time = _kst_wall_time(reference_now)
    forecast_collected_at = snap.forecast_collected_at or doc.snapshot_as_of
    forecast_stale = _is_stale(
        forecast_collected_at, now=reference_now, max_age=_FORECAST_MAX_AGE
    )
    advisory_stale = snap.advisory.is_stale or _is_stale(
        doc.snapshot_as_of, now=reference_now, max_age=_ADVISORY_MAX_AGE
    )
    current_advisory = snap.advisory.model_copy(
        update={
            "is_missing": snap.advisory.is_missing or advisory_stale,
            "is_stale": advisory_stale,
        }
    )
    advisory = CurrentAdvisory(
        advisory=current_advisory,
        checked_at=doc.snapshot_as_of,
    )

    selected = next(
        (point for point in snap.forecast if point.time == requested_wall_time),
        None,
    )
    if not snap.forecast:
        data_state = PlanDataState.UNAVAILABLE
        conditions = None
    elif requested_wall_time <= now_wall_time or selected is None:
        data_state = PlanDataState.INVALID_TIME
        conditions = None
    else:
        grade = grade_point(selected)
        conditions = ForecastConditions(
            forecast_at=selected.time,
            grade=grade,
            citations=_forecast_citations(selected),
            has_missing_critical=grade is None,
        )
        # 상태 우선순위: unavailable → stale → partial → detailed.
        if forecast_stale or advisory_stale:
            data_state = PlanDataState.STALE
        elif grade is None or current_advisory.is_missing:
            data_state = PlanDataState.PARTIAL
        else:
            data_state = PlanDataState.READY

    return PlanBriefing(
        spot_id=spot.id,
        activity=intent.activity,
        requested_at=intent.requested_at,
        data_state=data_state,
        coverage_state=_coverage_for(data_state),
        forecast_conditions=conditions,
        current_advisory=advisory,
        action=_plan_action(data_state, conditions.grade if conditions else None),
        limitations=[
            "예보는 현장 통제나 입수 허가를 대신하지 않습니다.",
            "현재 특보는 선택 시각의 미래 상태를 보장하지 않습니다.",
        ],
        official_links=links_for(intent.activity),
        snapshot_as_of=doc.snapshot_as_of,
    )


def plan_options_for(
    spot: Spot,
    *,
    doc: SnapshotDoc | None = None,
    now: datetime | None = None,
) -> PlanOptions:
    """선택 UI에는 스냅샷에 실제 존재하는 미래 예보 시각만 제공한다."""
    doc = doc or get_snapshot()
    snap = doc.spot(spot.id)
    if snap is None:
        raise KeyError(spot.id)
    reference_now = now or datetime.now(_KST)
    now_wall_time = _kst_wall_time(reference_now)
    return PlanOptions(
        spot_id=spot.id,
        forecast_times=[point.time for point in snap.forecast if point.time > now_wall_time],
        forecast_status=snap.forecast_status,
        forecast_collected_at=snap.forecast_collected_at,
        snapshot_as_of=doc.snapshot_as_of,
    )


def resolve_spot(key: str) -> Spot | None:
    return get_spot(key)
