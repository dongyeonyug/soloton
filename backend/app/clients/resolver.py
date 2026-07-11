"""provider 선택 + 기존 KHOA/KMA 함수를 ProviderReading 으로 어댑트.

config.resolved_provider 로 Open-Meteo(키리스) 또는 KHOA/KMA(키 게이트) 결정.
Phase 2(열쇠 도착) 전환은 이 파일과 config 만으로 완결된다.
"""

from __future__ import annotations

from ..config import Settings, get_settings
from ..models import AdvisoryKind, Metric
from ..spots import Spot
from . import khoa, kma
from .base import MarineProvider, ProviderReading
from .openmeteo import OpenMeteoProvider

KHOA_KMA_LABELS: dict[Metric, str] = {
    Metric.WAVE_HEIGHT: "KHOA 바다누리(실측)",
    Metric.CURRENT_SPEED: "KHOA 바다누리(실측)",
    Metric.TIDE_LEVEL: "KHOA 조위관측소(실측)",
    Metric.WATER_TEMP: "KHOA 바다누리(실측)",
    Metric.WIND_SPEED: "KHOA 해양관측부이(실측)",
}


class KhoaKmaProvider:
    """공공데이터포털 KHOA(해양 실측) + 기상청(특보)."""

    name = "khoa"
    source_labels = KHOA_KMA_LABELS

    def __init__(self, khoa_key: str, kma_key: str, khoa_tide_key: str | None = None) -> None:
        self._khoa_key = khoa_key
        self._khoa_tide_key = khoa_tide_key or khoa_key
        self._kma_key = kma_key

    async def fetch_spot(self, spot: Spot) -> ProviderReading | None:
        khoa_raw = await khoa.fetch_spot(spot, self._khoa_key, self._khoa_tide_key)
        kma_raw = await kma.fetch_spot(spot, self._kma_key)
        if khoa_raw is None and kma_raw is None:
            return None

        metrics: dict[Metric, float] = {}
        if khoa_raw:
            metrics.update(khoa_raw)
        advisory = AdvisoryKind.NONE
        if kma_raw:
            adv = kma_raw.get("advisory", AdvisoryKind.NONE)
            advisory = AdvisoryKind(adv) if isinstance(adv, str) else adv

        return ProviderReading(
            metrics=metrics,
            advisory=advisory,
            supports_advisory=kma_raw is not None,
            advisory_is_missing=kma_raw is None,
        )


class HybridProvider:
    """KHOA 실측 우선 + 결측 지표는 Open-Meteo 예보로 백필. 특보는 KMA.

    부이가 파고/풍속 센서를 갖지 않는 지점(예: TW_0087)도 예보 백필로 등급을 낼 수
    있게 한다. 지표별 출처(실측/예보)는 metric_sources 로 명시해 UI/브리핑에서 구분한다
    (사용자 명시 선택 — CLAUDE.md '결측 추정 금지' 예외로서의 하이브리드 정책).
    """

    name = "hybrid"
    source_labels = KHOA_KMA_LABELS

    def __init__(self, khoa_key: str, kma_key: str, khoa_tide_key: str | None = None) -> None:
        self._official = KhoaKmaProvider(khoa_key, kma_key, khoa_tide_key)
        self._model = OpenMeteoProvider()

    async def fetch_spot(self, spot: Spot) -> ProviderReading | None:
        official = await self._official.fetch_spot(spot)
        model = await self._model.fetch_spot(spot)

        metrics: dict[Metric, float] = {}
        metric_sources: dict[Metric, str] = {}
        if official:
            for metric, value in official.metrics.items():
                metrics[metric] = value
                metric_sources[metric] = KHOA_KMA_LABELS.get(metric, "KHOA 실측")
        if model:
            for metric, value in model.metrics.items():
                if metric not in metrics:  # 실측 없을 때만 예보 백필
                    metrics[metric] = value
                    metric_sources[metric] = self._model.source_labels.get(
                        metric, "Open-Meteo 예보"
                    )
        if not metrics:
            return None

        if official is not None:
            advisory = official.advisory
            supports_advisory = official.supports_advisory
            advisory_is_missing = official.advisory_is_missing
        else:
            advisory = AdvisoryKind.NONE
            supports_advisory = False
            advisory_is_missing = False

        observed_at = (official.observed_at if official else None) or (
            model.observed_at if model else None
        )
        return ProviderReading(
            metrics=metrics,
            advisory=advisory,
            supports_advisory=supports_advisory,
            advisory_is_missing=advisory_is_missing,
            observed_at=observed_at,
            metric_sources=metric_sources,
        )


def get_provider(settings: Settings | None = None) -> MarineProvider:
    settings = settings or get_settings()
    provider = settings.resolved_provider
    if provider == "hybrid":
        return HybridProvider(
            settings.khoa_api_key,
            settings.kma_api_key,
            settings.effective_khoa_tide_api_key,
        )
    if provider == "khoa":
        return KhoaKmaProvider(
            settings.khoa_api_key,
            settings.kma_api_key,
            settings.effective_khoa_tide_api_key,
        )
    return OpenMeteoProvider()
