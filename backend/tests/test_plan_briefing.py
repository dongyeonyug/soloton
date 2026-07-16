"""Phase 1 물놀이 계획 브리핑의 결정형 계약.

선택 시각의 예보와 현재 특보를 섞지 않고, 결측·오래된 스냅샷·사라진 시각을
안전하다고 보정하지 않는지를 고정한다.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

import app.service as service
from app.ingest.cache import SnapshotDoc, SpotSnapshot
from app.models import (
    Advisory,
    AdvisoryKind,
    ForecastCollectionStatus,
    ForecastPoint,
    Grade,
    PlanActivity,
    PlanCoverageState,
    PlanDataState,
    PlanIntent,
)
from app.spots import get_spot

KST = ZoneInfo("Asia/Seoul")
SNAPSHOT_AT = datetime(2026, 7, 16, 0, 0, 0)  # UTC naive 저장 계약
NOW = datetime(2026, 7, 16, 9, 0, 0, tzinfo=KST)


def _intent(hour: int) -> PlanIntent:
    return PlanIntent(
        spot_id="haeundae",
        activity=PlanActivity.WATER_PLAY,
        requested_at=datetime(2026, 7, 16, hour, 0, 0, tzinfo=KST),
    )


def _doc(
    forecast: list[ForecastPoint],
    *,
    advisory: Advisory | None = None,
    forecast_status: ForecastCollectionStatus = ForecastCollectionStatus.AVAILABLE,
) -> SnapshotDoc:
    return SnapshotDoc(
        snapshot_as_of=SNAPSHOT_AT,
        source="test",
        spots={
            "haeundae": SpotSnapshot(
                observations=[],
                advisory=advisory or Advisory(kind=AdvisoryKind.NONE, source="기상청 특보"),
                forecast=forecast,
                forecast_status=forecast_status,
                forecast_collected_at=SNAPSHOT_AT,
            )
        },
    )


def _point(hour: int, wave: float | None = 0.5, wind: float | None = 5.0) -> ForecastPoint:
    return ForecastPoint(
        time=datetime(2026, 7, 16, hour, 0, 0),
        wave_height=wave,
        wind_speed=wind,
    )


def test_selected_forecast_grade_does_not_absorb_current_advisory():
    """현재 풍랑주의보는 미래 선택 시각의 예보 등급을 덮어쓰지 않는다."""
    doc = _doc(
        [_point(10)],
        advisory=Advisory(kind=AdvisoryKind.WIND_WAVE_WARNING, source="기상청 특보"),
    )

    briefing = service.build_plan_briefing(get_spot("haeundae"), _intent(10), doc=doc, now=NOW)

    assert briefing.data_state is PlanDataState.READY
    assert briefing.coverage_state is PlanCoverageState.DETAILED
    assert briefing.forecast_conditions is not None
    assert briefing.forecast_conditions.grade is Grade.SAFE
    assert briefing.current_advisory is not None
    assert briefing.current_advisory.advisory.kind is AdvisoryKind.WIND_WAVE_WARNING
    assert briefing.current_advisory.scope_label == "현재 기준 · 미래 보장 아님"


def test_missing_selected_forecast_metric_is_partial_not_invented():
    briefing = service.build_plan_briefing(
        get_spot("haeundae"), _intent(10), doc=_doc([_point(10, wave=None)]), now=NOW
    )

    assert briefing.data_state is PlanDataState.PARTIAL
    assert briefing.forecast_conditions is not None
    assert briefing.forecast_conditions.grade is None
    wave = next(
        citation
        for citation in briefing.forecast_conditions.citations
        if citation.label == "유의파고"
    )
    assert wave.is_missing is True
    assert wave.value is None
    assert "안전하다고 단정하지" in briefing.action


def test_stale_snapshot_precedes_other_available_plan_data():
    later_now = datetime(2026, 7, 16, 16, 1, 0, tzinfo=KST)
    doc = _doc([_point(17)])

    briefing = service.build_plan_briefing(
        get_spot("haeundae"), _intent(17), doc=doc, now=later_now
    )

    assert briefing.data_state is PlanDataState.STALE
    assert briefing.coverage_state is PlanCoverageState.STALE
    assert briefing.current_advisory is not None
    assert briefing.current_advisory.advisory.is_stale is True


def test_missing_or_outdated_selected_time_requires_reselection():
    briefing = service.build_plan_briefing(
        get_spot("haeundae"), _intent(11), doc=_doc([_point(10)]), now=NOW
    )

    assert briefing.data_state is PlanDataState.INVALID_TIME
    assert briefing.coverage_state is PlanCoverageState.INVALID_TIME
    assert briefing.forecast_conditions is None
    assert "다시 선택" in briefing.action


def test_no_forecast_collection_is_unavailable_not_nearest_time():
    briefing = service.build_plan_briefing(
        get_spot("haeundae"),
        _intent(10),
        doc=_doc([], forecast_status=ForecastCollectionStatus.SOURCE_TIMEOUT),
        now=NOW,
    )

    assert briefing.data_state is PlanDataState.UNAVAILABLE
    assert briefing.forecast_conditions is None


def test_plan_intent_requires_explicit_kst_offset():
    with pytest.raises(ValidationError, match="Asia/Seoul"):
        PlanIntent(
            spot_id="haeundae",
            activity=PlanActivity.WATER_PLAY,
            requested_at=datetime(2026, 7, 16, 10, 0, 0),
        )


def test_plan_builder_cannot_enter_legacy_llm_generation(monkeypatch):
    def unexpected_llm_path(*args, **kwargs):
        raise AssertionError("plan builder must not call generate_briefing")

    monkeypatch.setattr(service, "generate_briefing", unexpected_llm_path)

    briefing = service.build_plan_briefing(
        get_spot("haeundae"), _intent(10), doc=_doc([_point(10)]), now=NOW
    )

    assert briefing.forecast_conditions is not None
    assert briefing.official_links
    assert all(link.activity_scope is PlanActivity.WATER_PLAY for link in briefing.official_links)
    assert all(link.last_verified_at.tzinfo is None for link in briefing.official_links)
