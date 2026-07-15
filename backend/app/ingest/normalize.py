"""provider 관측(ProviderReading) → 정규화 스키마(MarineObservation/Advisory).

결측은 추정하지 않고 is_missing=True 로 표기(AC1). 지표별 observed_at 을 개별 세팅.

특보 부재 처리(핵심): provider 가 특보를 지원하지 않으면(supports_advisory=False,
예: Open-Meteo) 특보를 '없음(NONE, 결측 아님)'으로 둔다 — "특보 소스 없음"과 "특보
결측"을 구분해 SAFE 등급 붕괴를 막는다. 등급 결측-플로어는 파고/풍속(임계 지표)에만
계속 적용된다. reading 자체가 None(전량 수집 실패)이면 특보도 결측으로 본다(이 경우
파고/풍속도 결측이라 어차피 플로어된다).
"""

from __future__ import annotations

from datetime import datetime

from ..clients.base import ProviderReading
from ..models import (
    Advisory,
    AdvisoryKind,
    MarineObservation,
    Metric,
    MissingReason,
)
from ..spots import Spot, tide_reference_for

UNITS: dict[Metric, str] = {
    Metric.WAVE_HEIGHT: "m",
    Metric.WIND_SPEED: "m/s",
    Metric.CURRENT_SPEED: "m/s",
    Metric.TIDE_LEVEL: "cm",
    Metric.WATER_TEMP: "°C",
}
# provider 가 라벨을 안 주는 지표의 기본 출처
DEFAULT_SOURCE = "공공 해양데이터"
# 정규화 대상 지표(참고 지표 포함)
ALL_METRICS: tuple[Metric, ...] = (
    Metric.WAVE_HEIGHT,
    Metric.WIND_SPEED,
    Metric.CURRENT_SPEED,
    Metric.TIDE_LEVEL,
    Metric.WATER_TEMP,
)


def normalize_spot(
    spot: Spot,
    reading: ProviderReading | None,
    fetched_at: datetime,
    *,
    source_labels: dict[Metric, str] | None = None,
    collection_failure: MissingReason | None = None,
) -> tuple[list[MarineObservation], Advisory]:
    """provider 결과 → 관측 리스트 + 특보. 없는 값은 결측."""
    source_labels = source_labels or {}
    values = reading.metrics if reading else {}
    metric_sources = reading.metric_sources if reading else {}
    metric_missing_reasons = reading.metric_missing_reasons if reading else {}
    observed_at = reading.observed_at if reading else None
    metric_observed_at = reading.metric_observed_at if reading else {}
    tide_reference = tide_reference_for(spot)

    observations: list[MarineObservation] = []
    for metric in ALL_METRICS:
        val = values.get(metric)
        # 지표별 출처: reading.metric_sources(하이브리드 실측/예보) > provider 라벨 > 기본
        source = metric_sources.get(metric) or source_labels.get(metric, DEFAULT_SOURCE)
        metric_time = metric_observed_at.get(metric, observed_at)
        reference_station_name = None
        reference_station_code = None
        reference_distance_km = None
        if metric is Metric.TIDE_LEVEL and tide_reference is not None:
            station, reference_distance_km = tide_reference
            reference_station_name = station.name
            reference_station_code = station.code
        missing_reason = None
        if val is None:
            if reading is None:
                missing_reason = collection_failure or MissingReason.SOURCE_UNAVAILABLE
            else:
                missing_reason = metric_missing_reasons.get(metric)
                if missing_reason is None and metric is Metric.TIDE_LEVEL and not spot.khoa_tide_obs_code:
                    missing_reason = MissingReason.NO_STATION_MAPPING
                if missing_reason is None:
                    missing_reason = MissingReason.SOURCE_RETURNED_NO_VALUE
        observations.append(
            MarineObservation(
                spot_id=spot.id,
                metric=metric,
                value=val,
                unit=UNITS[metric],
                observed_at=metric_time if val is not None else None,
                source=source,
                is_missing=val is None,
                missing_reason=missing_reason,
                fetched_at=fetched_at,
                reference_station_name=reference_station_name,
                reference_station_code=reference_station_code,
                reference_distance_km=reference_distance_km,
            )
        )

    if reading is None:
        # 전량 수집 실패 → 특보 결측(파고/풍속 결측이 이미 플로어)
        advisory = Advisory(kind=AdvisoryKind.NONE, source="특보 소스 없음", is_missing=True)
    elif reading.advisory_is_missing:
        advisory = Advisory(
            kind=AdvisoryKind.NONE,
            source="기상청 특보 수집 실패",
            is_missing=True,
        )
    elif reading.supports_advisory:
        kind = reading.advisory
        advisory = Advisory(
            kind=kind,
            effective_at=observed_at if kind is not AdvisoryKind.NONE else None,
            source="기상청 특보",
            is_missing=False,
        )
    else:
        # 특보 미지원 provider → '없음'(결측 아님) → SAFE 붕괴 방지
        advisory = Advisory(kind=AdvisoryKind.NONE, source="특보 소스 미제공", is_missing=False)
    return observations, advisory


def observations_to_map(observations: list[MarineObservation]) -> dict[Metric, MarineObservation]:
    return {obs.metric: obs for obs in observations}
