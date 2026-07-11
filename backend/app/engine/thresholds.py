"""위험도 임계값 — 데이터주도, 모든 값에 source 동반.

여기의 숫자가 사실의 원천이다. 문서 docs/RISK_THRESHOLDS.md 와 반드시 정렬한다.
활동 보정치는 citable source 필수 — 없으면 애초에 표에 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Activity, AdvisoryKind, Grade, Metric


@dataclass(frozen=True)
class Band:
    """[safe_below) SAFE, [safe_below, danger_at) CAUTION, [danger_at, ) DANGER."""

    safe_below: float
    danger_at: float
    unit: str
    source: str
    label: str

    def grade_for(self, value: float) -> Grade:
        if value < self.safe_below:
            return Grade.SAFE
        if value < self.danger_at:
            return Grade.CAUTION
        return Grade.DANGER


# 임계 지표 밴드 (등급 결정)
THRESHOLDS: dict[Metric, Band] = {
    Metric.WIND_SPEED: Band(
        safe_below=14.0, danger_at=21.0, unit="m/s", label="풍속",
        source="기상청 풍랑주의보(14m/s)·경보(21m/s) 기준",
    ),
    Metric.WAVE_HEIGHT: Band(
        safe_below=2.0, danger_at=3.0, unit="m", label="유의파고",
        source="기상청 풍랑주의보(3m)·경보(5m) 기준을 연안 보수화",
    ),
    Metric.CURRENT_SPEED: Band(
        safe_below=1.0, danger_at=2.0, unit="m/s", label="조류",
        source="소형선박/입수 안전 통용 기준(해커톤 매핑)",
    ),
}

# 참고 지표 — 등급에 기여하지 않으나 브리핑 슬롯으로 표기
REFERENCE_METRICS: dict[Metric, tuple[str, str]] = {
    Metric.TIDE_LEVEL: ("cm", "조위"),
    Metric.WATER_TEMP: ("°C", "수온"),
}

# 기상특보 → 최소 강제 등급 (자기 등급 이상으로 override)
ADVISORY_OVERRIDE: dict[AdvisoryKind, tuple[Grade, str]] = {
    AdvisoryKind.WIND_WAVE_WARNING: (Grade.CAUTION, "기상청 풍랑주의보 발효"),
    AdvisoryKind.WAVE_WARNING: (Grade.CAUTION, "기상청 풍파주의보 발효"),
    AdvisoryKind.WIND_WAVE_ALERT: (Grade.DANGER, "기상청 풍랑경보 발효"),
    AdvisoryKind.WAVE_ALERT: (Grade.DANGER, "기상청 풍파경보 발효"),
}


@dataclass(frozen=True)
class ActivityAdjust:
    """활동별 보정. 각 필드는 citable source 를 가진다."""

    wave_safe_below_delta: float = 0.0   # 파고 SAFE 임계 가산(음수=보수화)
    rock_danger_emphasis: bool = False   # 갯바위 고립/추락 강조
    source: str = ""


# 출처 없는 보정은 넣지 않는다.
ACTIVITY_ADJUST: dict[Activity, ActivityAdjust] = {
    Activity.SWIMMING: ActivityAdjust(
        wave_safe_below_delta=-0.5,
        source="입수 활동 파고 보수화(해커톤 매핑)",
    ),
    Activity.ROCK_FISHING: ActivityAdjust(
        rock_danger_emphasis=True,
        source="갯바위 고립·추락 위험 강조(해커톤 매핑)",
    ),
    Activity.FISHING: ActivityAdjust(source="풍랑특보 기준과 정렬"),
    Activity.LEISURE: ActivityAdjust(source="풍랑특보 기준과 정렬"),
}

# 결측 임계 지표가 강제하는 등급 하한(안전-치명적).
MISSING_CRITICAL_FLOOR: Grade = Grade.CAUTION

# 지표별 신선도 만료 (초). 초과 시 is_missing 으로 강등.
MAX_AGE_SECONDS: dict[Metric, int] = {
    Metric.WAVE_HEIGHT: 6 * 3600,
    Metric.WIND_SPEED: 6 * 3600,
    Metric.CURRENT_SPEED: 6 * 3600,
    Metric.TIDE_LEVEL: 6 * 3600,
    Metric.WATER_TEMP: 6 * 3600,
}
ADVISORY_MAX_AGE_SECONDS: int = 3 * 3600


def effective_wave_band(activity: Activity) -> Band:
    """활동 보정이 적용된 파고 밴드."""
    base = THRESHOLDS[Metric.WAVE_HEIGHT]
    adj = ACTIVITY_ADJUST.get(activity, ActivityAdjust())
    if adj.wave_safe_below_delta == 0.0:
        return base
    return Band(
        safe_below=base.safe_below + adj.wave_safe_below_delta,
        danger_at=base.danger_at,
        unit=base.unit,
        label=base.label,
        source=f"{base.source} + {adj.source}",
    )
