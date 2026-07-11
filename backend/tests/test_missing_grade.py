"""AC5a: 자백(등급) — 결측 임계 지표 → 등급 절대 안전 아님(CAUTION 이상 floor)."""

import pytest

from app.engine.risk import evaluate, mark_stale
from app.models import (
    Activity,
    Advisory,
    AdvisoryKind,
    Grade,
    MarineObservation,
    Metric,
)

from .helpers import FIXED_TIME, build_inputs

# 각 골드-ish 케이스에 임계 지표를 하나씩 결측 주입
MISSING_CASES = [
    ("wave-missing", {"wave": None, "wind": 5.0, "current": 0.2}),
    ("wind-missing", {"wave": 0.5, "wind": None, "current": 0.2}),
    ("both-missing", {"wave": None, "wind": None, "current": 0.2}),
    ("wave-missing-calm-everything", {"wave": None, "wind": 3.0, "current": 0.1}),
]


@pytest.mark.parametrize("name,case", MISSING_CASES, ids=[c[0] for c in MISSING_CASES])
def test_missing_critical_never_safe(name, case):
    full = {**case, "advisory": "none", "activity": "조업"}
    obs, adv, act = build_inputs(full)
    result = evaluate(obs, adv, act, "09-12")
    assert result.grade != Grade.SAFE
    assert result.grade.rank >= Grade.CAUTION.rank
    assert result.has_missing_critical is True


def test_missing_advisory_forces_floor():
    """특보 결측(모름) → 안전 불가."""
    case = {"wave": 0.5, "wind": 5.0, "current": 0.2, "advisory": "none", "activity": "조업"}
    obs, _, act = build_inputs(case)
    missing_adv = Advisory(kind=AdvisoryKind.NONE, source="KMA", is_missing=True)
    result = evaluate(obs, missing_adv, act, "09-12")
    assert result.grade != Grade.SAFE
    assert result.has_missing_critical is True


def test_missing_noncritical_current_stays_safe():
    """비임계 지표(조류) 결측은 floor 를 강제하지 않는다."""
    case = {"wave": 0.5, "wind": 5.0, "current": None, "advisory": "none", "activity": "조업"}
    obs, adv, act = build_inputs(case)
    result = evaluate(obs, adv, act, "09-12")
    assert result.grade == Grade.SAFE
    assert result.has_missing_critical is False


def test_freshness_expiry_becomes_missing():
    """신선도 만료 → is_missing 강등 → 안전 불가."""
    stale_time = FIXED_TIME.replace(hour=0)  # 9시간 전 (max_age 6h 초과)
    obs = {
        Metric.WAVE_HEIGHT: MarineObservation(
            spot_id="x", metric=Metric.WAVE_HEIGHT, value=0.5, unit="m",
            observed_at=stale_time, source="KHOA",
        ),
        Metric.WIND_SPEED: MarineObservation(
            spot_id="x", metric=Metric.WIND_SPEED, value=3.0, unit="m/s",
            observed_at=FIXED_TIME, source="KMA",
        ),
    }
    adv = Advisory(kind=AdvisoryKind.NONE, source="KMA")
    fresh_obs, fresh_adv = mark_stale(obs, adv, as_of=FIXED_TIME)
    assert fresh_obs[Metric.WAVE_HEIGHT].is_missing is True
    result = evaluate(fresh_obs, fresh_adv, Activity.FISHING, "09-12")
    assert result.grade != Grade.SAFE
    assert result.has_missing_critical is True
