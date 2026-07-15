"""파이프라인 조립 — 스냅샷 → 신선도 → 등급 → 브리핑. 라우터·테스트 공용.

C1 해소: 커밋 스냅샷 경로에서는 신선도 만료를 snapshot_as_of 기준으로 판정한다
(데모가 전부 '정보없음'으로 무너지지 않도록).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .briefing.generate import LLMFn, generate_briefing
from .engine.forecast import assess_forecast_window
from .engine.risk import evaluate, mark_stale
from .ingest.cache import SnapshotDoc, get_snapshot
from .models import (
    Briefing,
    ForecastCollectionStatus,
    ProseStatus,
    RiskGrade,
    SafeWindow,
    SafeWindowAssessment,
    SafeWindowStatus,
)
from .spots import Spot, get_spot

DEFAULT_TIME_SLOT = "현재"
# 예보 시계열 시각은 KST(Open-Meteo Asia/Seoul). '미래' 판정은 KST now 기준.
_KST = ZoneInfo("Asia/Seoul")


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


def resolve_spot(key: str) -> Spot | None:
    return get_spot(key)
