"""DAC3: 특보 미지원 provider(Open-Meteo)에서 특보 부재가 SAFE 를 붕괴시키지 않음."""

from datetime import datetime

from app.clients.base import ProviderReading
from app.engine.risk import evaluate
from app.ingest.normalize import normalize_spot, observations_to_map
from app.models import Activity, AdvisoryKind, Grade, Metric
from app.spots import get_spot

FIXED = datetime(2026, 7, 10, 9, 0, 0)


def _reading(supports_advisory: bool, advisory=AdvisoryKind.NONE) -> ProviderReading:
    return ProviderReading(
        metrics={
            Metric.WAVE_HEIGHT: 0.5,
            Metric.WIND_SPEED: 5.0,
            Metric.CURRENT_SPEED: 0.2,
        },
        advisory=advisory,
        supports_advisory=supports_advisory,
        observed_at=FIXED,
    )


def test_advisory_unsupported_not_missing():
    spot = get_spot("haeundae")
    _, advisory = normalize_spot(spot, _reading(False), fetched_at=FIXED)
    assert advisory.is_missing is False
    assert advisory.kind is AdvisoryKind.NONE


def test_safe_survives_without_advisory_source():
    """캄 데이터 + 특보 소스 없음 → SAFE (CAUTION 붕괴 금지)."""
    spot = get_spot("haeundae")
    obs_list, advisory = normalize_spot(spot, _reading(False), fetched_at=FIXED)
    obs = observations_to_map(obs_list)
    result = evaluate(obs, advisory, Activity.LEISURE, "현재")
    assert result.grade == Grade.SAFE
    assert result.has_missing_critical is False


def test_missing_wave_still_floors_without_advisory():
    """특보 소스 없어도 파고 결측은 여전히 안전 불가(무환각 floor 유지)."""
    spot = get_spot("haeundae")
    reading = _reading(False)
    del reading.metrics[Metric.WAVE_HEIGHT]  # 파고 결측 주입
    obs_list, advisory = normalize_spot(spot, reading, fetched_at=FIXED)
    obs = observations_to_map(obs_list)
    result = evaluate(obs, advisory, Activity.LEISURE, "현재")
    assert result.grade != Grade.SAFE
    assert result.has_missing_critical is True


def test_supported_advisory_still_escalates():
    """특보 지원 provider 에서 경보는 여전히 등급 상향."""
    spot = get_spot("haeundae")
    reading = _reading(True, advisory=AdvisoryKind.WIND_WAVE_ALERT)
    obs_list, advisory = normalize_spot(spot, reading, fetched_at=FIXED)
    obs = observations_to_map(obs_list)
    result = evaluate(obs, advisory, Activity.LEISURE, "현재")
    assert result.grade == Grade.DANGER


def test_advisory_fetch_failure_is_explicitly_missing():
    spot = get_spot("haeundae")
    reading = _reading(False)
    reading.advisory_is_missing = True
    _, advisory = normalize_spot(spot, reading, fetched_at=FIXED)
    assert advisory.is_missing is True
    assert advisory.source == "기상청 특보 수집 실패"
