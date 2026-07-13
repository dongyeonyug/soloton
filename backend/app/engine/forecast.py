"""'가장 안전한 시간' 계산 — 순수함수. I/O·시계·난수 없음(엔진 순수성 유지).

예보 시계열(ForecastPoint)의 각 시각을 기존 등급 밴드로 채점하고, 미래 구간에서
가장 이른 '최선'(SAFE 우선, 없으면 CAUTION) 연속 시간창을 고른다. `now` 를 명시
인자로 받아 결정론을 유지한다. 시각은 코드가 소유하며 LLM 은 생성하지 않는다(불변식).

전부 DANGER 이거나 등급 산정 가능한 미래 시각이 없으면 None → '안전한 시간 없음'을
정직하게 자백(추정 금지).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..models import Activity, ForecastPoint, Grade, Metric, SafeWindow
from .thresholds import THRESHOLDS, effective_wave_band

DEFAULT_HORIZON = timedelta(hours=12)
# 인접 예보점 간 최대 간격. 이보다 벌어지면 연속창이 끊긴다(결측 hour 등).
_MAX_GAP = timedelta(minutes=90)


def _worst(a: Grade, b: Grade) -> Grade:
    return a if a.rank >= b.rank else b


def grade_point(point: ForecastPoint, activity: Activity) -> Grade | None:
    """한 시각의 등급. 파고·풍속 둘 다 있어야 하며, 하나라도 결측이면 None(추정 금지)."""
    if point.wave_height is None or point.wind_speed is None:
        return None
    wave = effective_wave_band(activity).grade_for(point.wave_height)
    wind = THRESHOLDS[Metric.WIND_SPEED].grade_for(point.wind_speed)
    return _worst(wave, wind)


def safest_window(
    series: list[ForecastPoint],
    activity: Activity,
    *,
    now: datetime,
    horizon: timedelta = DEFAULT_HORIZON,
) -> SafeWindow | None:
    """미래 구간에서 가장 이른 '최선' 연속 시간창. 없으면 None."""
    graded: list[tuple[datetime, Grade]] = []
    for point in sorted(series, key=lambda p: p.time):
        if point.time < now or point.time > now + horizon:
            continue
        grade = grade_point(point, activity)
        if grade is not None:
            graded.append((point.time, grade))
    if not graded:
        return None

    # 목표 등급: SAFE 있으면 SAFE, 없으면 CAUTION, 전부 DANGER 면 None(자백).
    ranks = {g.rank for _, g in graded}
    if Grade.SAFE.rank in ranks:
        target = Grade.SAFE
    elif Grade.CAUTION.rank in ranks:
        target = Grade.CAUTION
    else:
        return None

    # target 등급의 연속 run 들 중 가장 이른 것(시간 오름차순 순회이므로 runs[0]).
    runs: list[list[datetime]] = []
    current: list[datetime] = []
    prev: datetime | None = None
    for t, grade in graded:
        gap_break = prev is not None and (t - prev) > _MAX_GAP
        if grade == target and not gap_break:
            current.append(t)
        elif grade == target:  # target 이지만 간격 끊김 → 새 run
            if current:
                runs.append(current)
            current = [t]
        else:  # 다른 등급 → 진행 중 run 종료
            if current:
                runs.append(current)
                current = []
        prev = t
    if current:
        runs.append(current)

    first = runs[0]
    return SafeWindow(start=first[0], end=first[-1], grade=target)
