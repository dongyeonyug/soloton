"""위험도 임계값 — 데이터주도, 모든 값에 source 동반.

여기의 숫자가 사실의 원천이다. 문서 docs/RISK_THRESHOLDS.md 와 반드시 정렬한다.
활동별 보정은 근거가 검증되지 않아 사용하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import AdvisoryKind, Grade, Metric, RuleEvidence


@dataclass(frozen=True)
class Band:
    """[safe_below) SAFE, [safe_below, danger_at) CAUTION, [danger_at, ) DANGER."""

    safe_below: float
    danger_at: float
    unit: str
    source: str
    label: str
    evidence: RuleEvidence

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
        source="기상청 풍랑특보 풍속 수치(14m/s·21m/s)를 단일 시점 비교용으로 보수 적용",
        evidence=RuleEvidence.CONSERVATIVE_MAPPING,
    ),
    Metric.WAVE_HEIGHT: Band(
        safe_below=2.0, danger_at=3.0, unit="m", label="유의파고",
        source="기상청 풍랑주의보(3m)·경보(5m) 기준을 연안 보수화",
        evidence=RuleEvidence.CONSERVATIVE_MAPPING,
    ),
}

# 참고 지표 — 수치·출처를 보이되 최종 등급에는 기여하지 않는다.
# 조류는 지역·활동별 검증 임계값을 확보하기 전까지 이 범주로 둔다.
REFERENCE_METRICS: dict[Metric, tuple[str, str, str]] = {
    Metric.CURRENT_SPEED: (
        "m/s",
        "조류",
        "지역·활동별 검증 임계값이 없어 등급에 반영하지 않음",
    ),
    Metric.TIDE_LEVEL: ("cm", "조위", "현재 위험도 등급에는 반영하지 않는 참고값"),
    Metric.WATER_TEMP: ("°C", "수온", "현재 위험도 등급에는 반영하지 않는 참고값"),
}

# 기상특보 → 최소 강제 등급 (자기 등급 이상으로 override)
ADVISORY_OVERRIDE: dict[AdvisoryKind, tuple[Grade, str]] = {
    AdvisoryKind.WIND_WAVE_WARNING: (Grade.CAUTION, "기상청 풍랑주의보 발효"),
    AdvisoryKind.WAVE_WARNING: (Grade.CAUTION, "기상청 풍파주의보 발효"),
    AdvisoryKind.WIND_WAVE_ALERT: (Grade.DANGER, "기상청 풍랑경보 발효"),
    AdvisoryKind.WAVE_ALERT: (Grade.DANGER, "기상청 풍파경보 발효"),
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
