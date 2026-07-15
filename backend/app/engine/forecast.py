"""'가장 안전한 시간' 계산 — 순수함수. I/O·시계·난수 없음(엔진 순수성 유지).

예보 시계열(ForecastPoint)의 각 시각을 기존 등급 밴드로 채점하고, 미래 구간에서
가장 이른 '최선'(SAFE 우선, 없으면 CAUTION) 연속 시간창을 고른다. `now` 를 명시
인자로 받아 결정론을 유지한다. 시각은 코드가 소유하며 LLM 은 생성하지 않는다(불변식).

전부 DANGER 이거나 등급 산정 가능한 미래 시각이 없으면 None → '안전한 시간 없음'을
정직하게 자백(추정 금지).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..models import (
    ForecastPoint,
    Grade,
    Metric,
    SafeWindow,
    SafeWindowAssessment,
    SafeWindowStatus,
)
from .thresholds import THRESHOLDS

DEFAULT_HORIZON = timedelta(hours=12)
SELECTION_RULE = "안전 시각을 우선하고, 없으면 주의 시각 중 가장 이른 연속 구간을 선택"
# 인접 예보점 간 최대 간격. 이보다 벌어지면 연속창이 끊긴다(결측 hour 등).
_MAX_GAP = timedelta(minutes=90)


def _worst(a: Grade, b: Grade) -> Grade:
    return a if a.rank >= b.rank else b


def grade_point(point: ForecastPoint) -> Grade | None:
    """한 시각의 등급. 파고·풍속 둘 다 있어야 하며, 하나라도 결측이면 None(추정 금지)."""
    if point.wave_height is None or point.wind_speed is None:
        return None
    wave = THRESHOLDS[Metric.WAVE_HEIGHT].grade_for(point.wave_height)
    wind = THRESHOLDS[Metric.WIND_SPEED].grade_for(point.wind_speed)
    return _worst(wave, wind)


def assess_forecast_window(
    series: list[ForecastPoint],
    *,
    now: datetime,
    horizon: timedelta = DEFAULT_HORIZON,
) -> SafeWindowAssessment:
    """시간대 선택과 계산 불가 사유를 함께 반환하는 순수 평가."""
    considered_points = 0
    graded: list[tuple[datetime, Grade]] = []
    for point in sorted(series, key=lambda p: p.time):
        if point.time < now or point.time > now + horizon:
            continue
        considered_points += 1
        grade = grade_point(point)
        if grade is not None:
            graded.append((point.time, grade))
    if not graded:
        status = (
            SafeWindowStatus.NO_FUTURE_FORECAST
            if considered_points == 0
            else SafeWindowStatus.INCOMPLETE_FORECAST
        )
        detail = (
            "평가 지평 안에 미래 예보 시각이 없어 시간대를 계산하지 않았습니다."
            if status is SafeWindowStatus.NO_FUTURE_FORECAST
            else "파고와 풍속이 함께 있는 예보 시각이 없어 시간대를 계산하지 않았습니다."
        )
        return SafeWindowAssessment(
            status=status,
            detail=detail,
            horizon_hours=round(horizon.total_seconds() / 3600),
            forecast_points_collected=len(series),
            forecast_points_considered=considered_points,
            forecast_points_graded=0,
            selection_rule=SELECTION_RULE,
        )

    # 목표 등급: SAFE 있으면 SAFE, 없으면 CAUTION, 전부 DANGER 면 None(자백).
    ranks = {g.rank for _, g in graded}
    if Grade.SAFE.rank in ranks:
        target = Grade.SAFE
    elif Grade.CAUTION.rank in ranks:
        target = Grade.CAUTION
    else:
        return SafeWindowAssessment(
            status=SafeWindowStatus.NO_SAFE_WINDOW,
            detail="평가 가능한 미래 예보 시각이 모두 위험으로 분류되어 시간대를 제시하지 않습니다.",
            horizon_hours=round(horizon.total_seconds() / 3600),
            forecast_points_collected=len(series),
            forecast_points_considered=considered_points,
            forecast_points_graded=len(graded),
            selection_rule=SELECTION_RULE,
        )

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
    safe_window = SafeWindow(
        start=first[0],
        end=first[-1],
        grade=target,
        horizon_hours=round(horizon.total_seconds() / 3600),
        forecast_points_considered=considered_points,
        forecast_points_graded=len(graded),
        selected_points=len(first),
        selection_rule=SELECTION_RULE,
    )
    return SafeWindowAssessment(
        status=SafeWindowStatus.AVAILABLE,
        detail="시간별 파고와 풍속을 평가해 가장 이른 최선의 연속 구간을 선택했습니다.",
        horizon_hours=safe_window.horizon_hours,
        forecast_points_collected=len(series),
        forecast_points_considered=considered_points,
        forecast_points_graded=len(graded),
        selection_rule=SELECTION_RULE,
        safe_window=safe_window,
    )


def safest_window(
    series: list[ForecastPoint],
    *,
    now: datetime,
    horizon: timedelta = DEFAULT_HORIZON,
) -> SafeWindow | None:
    """호환용 선택 결과. 새 호출부는 assess_forecast_window를 사용한다."""
    return assess_forecast_window(series, now=now, horizon=horizon).safe_window
