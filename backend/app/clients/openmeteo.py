"""Open-Meteo provider (키리스, 무료·비상업).

Marine API(파고·조류·수온) + Forecast API(풍속) 병합. 좌표만 있으면 되어 관측소 코드
불필요. 데이터는 세계 수치예보 모델(MFWAM/ECMWF/GFS-Wave 등)의 **예측값**이며 실측이
아니다(DISCLAIMER 고지). 기상특보는 제공하지 않음 → supports_advisory=False.

조류 유속은 Open-Meteo 가 km/h 로 주므로 m/s 로 변환(÷3.6)한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import ForecastPoint, Metric
from ..spots import Spot
from .base import ProviderReading, fetch_json

# 안전시간 예보 지평(일). 12h horizon 을 넉넉히 덮도록 2일치 hourly 를 받는다.
FORECAST_DAYS = 2

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

KMH_TO_MS = 1.0 / 3.6

SOURCE_LABELS: dict[Metric, str] = {
    Metric.WAVE_HEIGHT: "Open-Meteo 해양모델(MFWAM/ECMWF)",
    Metric.CURRENT_SPEED: "Open-Meteo 해양모델(MFWAM/ECMWF)",
    Metric.WATER_TEMP: "Open-Meteo 해양모델",
    Metric.WIND_SPEED: "Open-Meteo 기상모델",
}


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_time(v: Any) -> datetime | None:
    if not isinstance(v, str):
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


class OpenMeteoProvider:
    name = "openmeteo"
    source_labels = SOURCE_LABELS

    async def fetch_spot(self, spot: Spot) -> ProviderReading | None:
        marine = await fetch_json(
            MARINE_URL,
            params={
                "latitude": spot.lat,
                "longitude": spot.lng,
                "current": "wave_height,ocean_current_velocity,sea_surface_temperature",
                "timezone": "Asia/Seoul",
            },
        )
        forecast = await fetch_json(
            FORECAST_URL,
            params={
                "latitude": spot.lat,
                "longitude": spot.lng,
                "current": "wind_speed_10m",
                "wind_speed_unit": "ms",
                "timezone": "Asia/Seoul",
            },
        )
        if marine is None and forecast is None:
            return None

        metrics: dict[Metric, float] = {}
        observed_at: datetime | None = None

        cur = (marine or {}).get("current") or {}
        observed_at = _parse_time(cur.get("time")) or observed_at
        wave = _to_float(cur.get("wave_height"))
        if wave is not None:
            metrics[Metric.WAVE_HEIGHT] = wave
        current_kmh = _to_float(cur.get("ocean_current_velocity"))
        if current_kmh is not None:
            metrics[Metric.CURRENT_SPEED] = round(current_kmh * KMH_TO_MS, 3)
        temp = _to_float(cur.get("sea_surface_temperature"))
        if temp is not None:
            metrics[Metric.WATER_TEMP] = temp

        fcur = (forecast or {}).get("current") or {}
        observed_at = observed_at or _parse_time(fcur.get("time"))
        wind = _to_float(fcur.get("wind_speed_10m"))
        if wind is not None:
            metrics[Metric.WIND_SPEED] = wind

        if not metrics:
            return None
        return ProviderReading(
            metrics=metrics,
            supports_advisory=False,
            observed_at=observed_at,
        )

    @staticmethod
    def _hourly_map(payload: Any, key: str) -> dict[datetime, float | None]:
        """Open-Meteo hourly 응답 → {시각: 값}. 결측값은 None 유지(추정 금지)."""
        hourly = (payload or {}).get("hourly") or {}
        times = hourly.get("time") or []
        values = hourly.get(key) or []
        out: dict[datetime, float | None] = {}
        for ts, val in zip(times, values):
            t = _parse_time(ts)
            if t is not None:
                out[t] = _to_float(val)
        return out

    async def fetch_forecast_series(self, spot: Spot) -> list[ForecastPoint]:
        """'가장 안전한 시간' 산정용 시간별 예보(파고+풍속). 실패 시 빈 리스트."""
        marine = await fetch_json(
            MARINE_URL,
            params={
                "latitude": spot.lat,
                "longitude": spot.lng,
                "hourly": "wave_height",
                "timezone": "Asia/Seoul",
                "forecast_days": FORECAST_DAYS,
            },
        )
        forecast = await fetch_json(
            FORECAST_URL,
            params={
                "latitude": spot.lat,
                "longitude": spot.lng,
                "hourly": "wind_speed_10m",
                "wind_speed_unit": "ms",
                "timezone": "Asia/Seoul",
                "forecast_days": FORECAST_DAYS,
            },
        )
        waves = self._hourly_map(marine, "wave_height")
        winds = self._hourly_map(forecast, "wind_speed_10m")
        times = sorted(set(waves) | set(winds))
        return [
            ForecastPoint(time=t, wave_height=waves.get(t), wind_speed=winds.get(t))
            for t in times
        ]
