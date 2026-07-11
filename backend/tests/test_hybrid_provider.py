"""하이브리드 provider — KHOA 실측 우선 + 결측 지표 Open-Meteo 예보 백필 + 지표별 출처."""

import asyncio

from app.clients import resolver
from app.clients.base import ProviderReading
from app.ingest.normalize import normalize_spot, observations_to_map
from app.models import AdvisoryKind, Metric
from app.spots import get_spot


def _install(monkeypatch, official: ProviderReading | None, model: ProviderReading | None):
    class FakeOfficial:
        name = "khoa"
        source_labels = resolver.KHOA_KMA_LABELS

        async def fetch_spot(self, spot):
            return official

    class FakeModel:
        name = "openmeteo"
        source_labels = {
            Metric.WAVE_HEIGHT: "Open-Meteo 해양모델",
            Metric.WIND_SPEED: "Open-Meteo 기상모델",
            Metric.CURRENT_SPEED: "Open-Meteo 해양모델",
            Metric.WATER_TEMP: "Open-Meteo 해양모델",
        }

        async def fetch_spot(self, spot):
            return model

    monkeypatch.setattr(resolver, "KhoaKmaProvider", lambda *a, **k: FakeOfficial())
    monkeypatch.setattr(resolver, "OpenMeteoProvider", lambda *a, **k: FakeModel())
    return resolver.HybridProvider("k", "m")


def test_backfills_missing_wave_wind_from_model(monkeypatch):
    # TW_0087 유형: KHOA 는 유속·수온만, 파고·풍속 없음
    official = ProviderReading(
        metrics={Metric.CURRENT_SPEED: 0.4, Metric.WATER_TEMP: 20.0},
        advisory=AdvisoryKind.NONE, supports_advisory=True, advisory_is_missing=False,
    )
    model = ProviderReading(
        metrics={Metric.WAVE_HEIGHT: 0.5, Metric.WIND_SPEED: 5.0,
                 Metric.CURRENT_SPEED: 9.9, Metric.WATER_TEMP: 99.0},
        supports_advisory=False,
    )
    provider = _install(monkeypatch, official, model)
    reading = asyncio.run(provider.fetch_spot(get_spot("busanhang")))

    # 파고·풍속은 예보 백필, 유속·수온은 실측 유지(모델값으로 덮어쓰지 않음)
    assert reading.metrics[Metric.WAVE_HEIGHT] == 0.5
    assert reading.metrics[Metric.WIND_SPEED] == 5.0
    assert reading.metrics[Metric.CURRENT_SPEED] == 0.4
    assert reading.metrics[Metric.WATER_TEMP] == 20.0
    # 지표별 출처: 실측 vs 예보 구분
    assert "실측" in reading.metric_sources[Metric.CURRENT_SPEED]
    assert "Open-Meteo" in reading.metric_sources[Metric.WAVE_HEIGHT]
    # 특보는 KHOA/KMA 경로 유지
    assert reading.supports_advisory is True


def test_source_labels_flow_into_observations(monkeypatch):
    official = ProviderReading(
        metrics={Metric.CURRENT_SPEED: 0.4}, supports_advisory=True,
    )
    model = ProviderReading(
        metrics={Metric.WAVE_HEIGHT: 0.5, Metric.WIND_SPEED: 5.0}, supports_advisory=False,
    )
    provider = _install(monkeypatch, official, model)
    spot = get_spot("busanhang")
    reading = asyncio.run(provider.fetch_spot(spot))
    obs = observations_to_map(normalize_spot(spot, reading, fetched_at=reading.observed_at)[0])
    assert "실측" in obs[Metric.CURRENT_SPEED].source
    assert "Open-Meteo" in obs[Metric.WAVE_HEIGHT].source
    assert obs[Metric.WAVE_HEIGHT].is_missing is False


def test_official_none_falls_back_to_model_without_advisory_floor(monkeypatch):
    # KHOA·KMA 전량 실패 → 예보만, 특보는 '없음(결측 아님)' → SAFE 붕괴 없음
    model = ProviderReading(
        metrics={Metric.WAVE_HEIGHT: 0.5, Metric.WIND_SPEED: 5.0}, supports_advisory=False,
    )
    provider = _install(monkeypatch, None, model)
    reading = asyncio.run(provider.fetch_spot(get_spot("busanhang")))
    assert reading.metrics[Metric.WAVE_HEIGHT] == 0.5
    assert reading.supports_advisory is False
    assert reading.advisory_is_missing is False


def test_all_missing_returns_none(monkeypatch):
    provider = _install(monkeypatch, None, None)
    assert asyncio.run(provider.fetch_spot(get_spot("busanhang"))) is None
