"""DAC1: Open-Meteo 어댑터 — 필드 매핑 + 단위 변환(조류 km/h→m/s) 검증."""

import asyncio

import pytest

from app.clients import openmeteo
from app.clients.openmeteo import ForecastSourceUnavailableError, OpenMeteoProvider
from app.ingest.normalize import normalize_spot
from app.models import Metric, MissingReason
from app.spots import get_spot

MARINE_FIXTURE = {
    "current": {
        "time": "2026-07-10T15:15",
        "wave_height": 0.32,
        "ocean_current_velocity": 5.1,  # km/h
        "sea_surface_temperature": 24.0,
    }
}
FORECAST_FIXTURE = {"current": {"time": "2026-07-10T15:15", "wind_speed_10m": 1.5}}


@pytest.fixture
def patched_fetch(monkeypatch):
    async def fake_fetch(url, params=None, **kwargs):
        if "marine" in url:
            return MARINE_FIXTURE
        return FORECAST_FIXTURE

    monkeypatch.setattr(openmeteo, "fetch_json", fake_fetch)


def test_openmeteo_maps_fields_and_converts_units(patched_fetch):
    spot = get_spot("haeundae")
    reading = asyncio.run(OpenMeteoProvider().fetch_spot(spot))
    assert reading is not None
    assert reading.metrics[Metric.WAVE_HEIGHT] == 0.32
    assert reading.metrics[Metric.WATER_TEMP] == 24.0
    assert reading.metrics[Metric.WIND_SPEED] == 1.5
    # 조류 5.1 km/h → 1.417 m/s (÷3.6)
    assert reading.metrics[Metric.CURRENT_SPEED] == pytest.approx(1.417, abs=0.001)
    assert reading.supports_advisory is False
    assert reading.observed_at is not None


def test_openmeteo_normalized_schema(patched_fetch):
    spot = get_spot("haeundae")
    reading = asyncio.run(OpenMeteoProvider().fetch_spot(spot))
    observations, advisory = normalize_spot(
        spot, reading, fetched_at=reading.observed_at,
        source_labels=OpenMeteoProvider.source_labels,
    )
    by_metric = {o.metric: o for o in observations}
    # 파고/풍속/조류/수온 present, 조위는 Open-Meteo 미제공 → 결측
    assert by_metric[Metric.WAVE_HEIGHT].is_missing is False
    assert by_metric[Metric.WIND_SPEED].value == 1.5
    assert by_metric[Metric.TIDE_LEVEL].is_missing is True
    assert by_metric[Metric.TIDE_LEVEL].missing_reason is MissingReason.SOURCE_NOT_SUPPORTED
    # Open-Meteo 출처 라벨 반영
    assert "Open-Meteo" in by_metric[Metric.WAVE_HEIGHT].source


def test_openmeteo_total_failure_returns_none(monkeypatch):
    async def fail(url, params=None, **kwargs):
        return None

    monkeypatch.setattr(openmeteo, "fetch_json", fail)
    reading = asyncio.run(OpenMeteoProvider().fetch_spot(get_spot("haeundae")))
    assert reading is None


def test_hourly_forecast_total_failure_has_distinct_signal(monkeypatch):
    """T6: 시간별 예보 소스 장애를 빈 응답과 섞지 않는다."""
    async def fail(url, params=None, **kwargs):
        return None

    monkeypatch.setattr(openmeteo, "fetch_json", fail)
    with pytest.raises(ForecastSourceUnavailableError):
        asyncio.run(OpenMeteoProvider().fetch_forecast_series(get_spot("haeundae")))
