"""provider 선택 + 기존 KHOA/KMA 함수를 ProviderReading 으로 어댑트.

config.resolved_provider 로 Open-Meteo(키리스) 또는 KHOA/KMA(키 게이트) 결정.
Phase 2(열쇠 도착) 전환은 이 파일과 config 만으로 완결된다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from ..config import Settings, get_settings
from ..models import AdvisoryKind, Metric, MissingReason
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
KHOA_METRICS: tuple[Metric, ...] = (
    Metric.WAVE_HEIGHT,
    Metric.WIND_SPEED,
    Metric.CURRENT_SPEED,
    Metric.TIDE_LEVEL,
    Metric.WATER_TEMP,
)


class KhoaKmaProvider:
    """공공데이터포털 KHOA(해양 실측) + 기상청(특보)."""

    name = "khoa"
    source_labels = KHOA_KMA_LABELS

    def __init__(self, khoa_key: str, kma_key: str, khoa_tide_key: str | None = None) -> None:
        self._khoa_key = khoa_key
        self._khoa_tide_key = khoa_tide_key or khoa_key
        self._kma_key = kma_key
        # Provider 인스턴스는 collect_all 한 번에만 쓰인다. 같은 관측소/전국 특보를
        # 지점 수만큼 다시 호출하지 않도록 실행 범위의 in-flight 캐시를 둔다.
        self._buoy_tasks: dict[str, asyncio.Task[khoa.KhoaMetrics | None]] = {}
        self._tide_tasks: dict[str, asyncio.Task[khoa.KhoaMetrics | None]] = {}
        self._advisory_task: asyncio.Task[kma.CoastalAdvisoryScope | None] | None = None

    async def fetch_spot(self, spot: Spot) -> ProviderReading | None:
        # 각 소스는 독립적이므로 병렬로 기다린다. KMA는 전국 현황 하나를 공유한다.
        khoa_raw, kma_raw = await asyncio.gather(
            self._fetch_khoa_spot(spot),
            self._fetch_busan_advisory(),
        )
        if khoa_raw is None and kma_raw is None:
            return None

        metrics: dict[Metric, float] = {}
        metric_missing_reasons: dict[Metric, MissingReason] = {}
        metric_observed_at: dict[Metric, datetime] = {}
        if khoa_raw:
            metrics.update(khoa_raw)
            metric_observed_at.update(khoa_raw.metric_observed_at)
        elif khoa_raw is None:
            metric_missing_reasons.update(
                {metric: MissingReason.SOURCE_UNAVAILABLE for metric in KHOA_METRICS}
            )
        if not spot.khoa_tide_obs_code or spot.khoa_tide_obs_code.startswith("TBD_"):
            metric_missing_reasons[Metric.TIDE_LEVEL] = MissingReason.NO_STATION_MAPPING
        elif Metric.TIDE_LEVEL not in metrics and khoa_raw is not None:
            metric_missing_reasons[Metric.TIDE_LEVEL] = MissingReason.SOURCE_RETURNED_NO_VALUE
        advisory = AdvisoryKind.NONE
        if kma_raw:
            adv = kma_raw.get("advisory", AdvisoryKind.NONE)
            advisory = AdvisoryKind(adv) if isinstance(adv, str) else adv

        return ProviderReading(
            metrics=metrics,
            advisory=advisory,
            supports_advisory=kma_raw is not None,
            advisory_is_missing=kma_raw is None,
            observed_at=max(metric_observed_at.values()) if metric_observed_at else None,
            metric_observed_at=metric_observed_at,
            metric_missing_reasons=metric_missing_reasons,
        )

    async def _fetch_khoa_spot(self, spot: Spot) -> khoa.KhoaMetrics | None:
        buoy, tide = await asyncio.gather(
            self._shared_buoy(spot),
            self._shared_tide(spot),
        )
        if buoy is None and tide is None:
            return None
        metrics = khoa.KhoaMetrics()
        if buoy:
            metrics.update(buoy)
            metrics.metric_observed_at.update(buoy.metric_observed_at)
        if tide:
            metrics.update(tide)
            metrics.metric_observed_at.update(tide.metric_observed_at)
        return metrics or None

    async def _shared_buoy(self, spot: Spot) -> khoa.KhoaMetrics | None:
        code = spot.khoa_obs_code
        if not code or code.startswith("TBD_"):
            return None
        task = self._buoy_tasks.get(code)
        if task is None:
            task = asyncio.create_task(khoa.fetch_buoy_spot(spot, self._khoa_key))
            self._buoy_tasks[code] = task
        return await self._await_shared(task)

    async def _shared_tide(self, spot: Spot) -> khoa.KhoaMetrics | None:
        code = spot.khoa_tide_obs_code
        if not code or code.startswith("TBD_"):
            return None
        task = self._tide_tasks.get(code)
        if task is None:
            task = asyncio.create_task(khoa.fetch_tide_spot(spot, self._khoa_tide_key))
            self._tide_tasks[code] = task
        return await self._await_shared(task)

    async def _fetch_busan_advisory(self) -> dict[str, AdvisoryKind] | None:
        if self._advisory_task is None:
            self._advisory_task = asyncio.create_task(
                kma.fetch_busan_coastal_scope(self._kma_key)
            )
        scope = await self._await_shared(self._advisory_task)
        return {"advisory": scope.advisory} if scope is not None else None

    @staticmethod
    async def _await_shared(task: asyncio.Task):
        """한 지점의 timeout 취소가 공유 요청까지 취소하지 않도록 보호한다."""
        try:
            return await asyncio.shield(task)
        except Exception:
            return None


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
        official, model = await asyncio.gather(
            self._official.fetch_spot(spot),
            self._model.fetch_spot(spot),
        )

        metrics: dict[Metric, float] = {}
        metric_sources: dict[Metric, str] = {}
        metric_missing_reasons: dict[Metric, MissingReason] = {}
        metric_observed_at: dict[Metric, datetime] = {}
        if official:
            for metric, value in official.metrics.items():
                metrics[metric] = value
                metric_sources[metric] = KHOA_KMA_LABELS.get(metric, "KHOA 실측")
                if metric in official.metric_observed_at:
                    metric_observed_at[metric] = official.metric_observed_at[metric]
            metric_missing_reasons.update(official.metric_missing_reasons)
        if model:
            for metric, value in model.metrics.items():
                if metric not in metrics:  # 실측 없을 때만 예보 백필
                    metrics[metric] = value
                    metric_sources[metric] = self._model.source_labels.get(
                        metric, "Open-Meteo 예보"
                    )
                    model_observed_at = self._model_observed_at(model, metric)
                    if model_observed_at is not None:
                        metric_observed_at[metric] = model_observed_at
                    metric_missing_reasons.pop(metric, None)
        if not metrics:
            return None

        if Metric.TIDE_LEVEL not in metrics and Metric.TIDE_LEVEL not in metric_missing_reasons:
            metric_missing_reasons[Metric.TIDE_LEVEL] = (
                MissingReason.SOURCE_RETURNED_NO_VALUE
                if official is not None
                else MissingReason.SOURCE_UNAVAILABLE
            )

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
            metric_observed_at=metric_observed_at,
            metric_sources=metric_sources,
            metric_missing_reasons=metric_missing_reasons,
        )

    @staticmethod
    def _model_observed_at(
        model: ProviderReading,
        metric: Metric,
    ) -> datetime | None:
        return model.metric_observed_at.get(metric, model.observed_at)


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
