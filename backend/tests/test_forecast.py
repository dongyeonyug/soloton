"""E2 엔진: safest_window 순수함수 — 시간대별 등급 → 가장 이른 최선 연속창.

시각은 코드가 결정론적으로 계산한다(불변식). now 명시 → 시계 없음.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.engine.forecast import grade_point, safest_window
from app.models import Activity, ForecastPoint, Grade

NOW = datetime(2026, 7, 12, 9, 0, 0)
LEISURE = Activity.LEISURE


def _pt(hour_offset: int, wave: float | None, wind: float | None) -> ForecastPoint:
    return ForecastPoint(
        time=NOW + timedelta(hours=hour_offset), wave_height=wave, wind_speed=wind
    )


def test_grade_point_missing_returns_none():
    assert grade_point(_pt(0, None, 5.0), LEISURE) is None
    assert grade_point(_pt(0, 0.5, None), LEISURE) is None


def test_grade_point_worst_of_wave_and_wind():
    # 파고 SAFE(0.5<2.0), 풍속 DANGER(22>=21) → worst=DANGER
    assert grade_point(_pt(0, 0.5, 22.0), LEISURE) is Grade.DANGER


def test_picks_earliest_safe_run():
    series = [
        _pt(0, 0.5, 5.0),   # SAFE
        _pt(1, 0.6, 6.0),   # SAFE
        _pt(2, 0.7, 7.0),   # SAFE
        _pt(3, 2.5, 8.0),   # CAUTION(파고)
    ]
    w = safest_window(series, LEISURE, now=NOW)
    assert w is not None
    assert w.grade is Grade.SAFE
    assert w.start == NOW
    assert w.end == NOW + timedelta(hours=2)


def test_falls_back_to_caution_when_no_safe():
    series = [_pt(0, 2.5, 5.0), _pt(1, 2.6, 6.0)]  # 둘 다 CAUTION(파고)
    w = safest_window(series, LEISURE, now=NOW)
    assert w is not None
    assert w.grade is Grade.CAUTION
    assert w.start == NOW


def test_all_danger_returns_none():
    series = [_pt(0, 3.5, 25.0), _pt(1, 4.0, 26.0)]
    assert safest_window(series, LEISURE, now=NOW) is None


def test_missing_points_break_contiguity():
    series = [
        _pt(0, 0.5, 5.0),        # SAFE
        _pt(1, None, None),      # 결측 → 제외
        _pt(2, 0.5, 5.0),        # SAFE (2h 간격 → 연속 아님)
    ]
    w = safest_window(series, LEISURE, now=NOW)
    assert w is not None
    assert w.start == NOW
    assert w.end == NOW  # 첫 run 은 단일 시각(간격으로 끊김)


def test_past_points_excluded():
    series = [_pt(-1, 0.5, 5.0), _pt(1, 2.5, 5.0)]  # 과거 SAFE 제외 → 미래는 CAUTION 만
    w = safest_window(series, LEISURE, now=NOW)
    assert w is not None
    assert w.grade is Grade.CAUTION
    assert w.start == NOW + timedelta(hours=1)


def test_horizon_excludes_far_future():
    series = [_pt(20, 0.5, 5.0)]  # 12h 지평 밖
    assert safest_window(series, LEISURE, now=NOW) is None


def test_empty_series_returns_none():
    assert safest_window([], LEISURE, now=NOW) is None


# ── provider 파싱(네트워크 없음) ──
def test_openmeteo_hourly_map_parses_and_keeps_missing():
    from app.clients.openmeteo import OpenMeteoProvider

    payload = {
        "hourly": {
            "time": ["2026-07-12T09:00", "2026-07-12T10:00"],
            "wave_height": [0.5, None],
        }
    }
    m = OpenMeteoProvider._hourly_map(payload, "wave_height")
    assert m[datetime(2026, 7, 12, 9, 0)] == 0.5
    assert m[datetime(2026, 7, 12, 10, 0)] is None  # 결측 보존(추정 금지)


# ── 서빙 통합 ──
import json  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from app.ingest.cache import SnapshotDoc, SpotSnapshot  # noqa: E402
from app.models import (  # noqa: E402
    Advisory,
    AdvisoryKind,
    MarineObservation,
    Metric,
)
from app.service import brief_spot, safe_window_for  # noqa: E402
from app.spots import get_spot  # noqa: E402

_KST = ZoneInfo("Asia/Seoul")
_AS_OF = datetime(2026, 7, 12, 1, 0, 0)


def _obs(metric: Metric, value: float, unit: str) -> MarineObservation:
    return MarineObservation(
        spot_id="haeundae", metric=metric, value=value, unit=unit,
        observed_at=_AS_OF, source="테스트", is_missing=False,
    )


def _full_doc(forecast: list[ForecastPoint]) -> SnapshotDoc:
    return SnapshotDoc(
        snapshot_as_of=_AS_OF,
        source="test",
        spots={
            "haeundae": SpotSnapshot(
                observations=[
                    _obs(Metric.WAVE_HEIGHT, 0.4, "m"),
                    _obs(Metric.WIND_SPEED, 3.0, "m/s"),
                    _obs(Metric.CURRENT_SPEED, 0.2, "m/s"),
                    _obs(Metric.TIDE_LEVEL, 100.0, "cm"),
                    _obs(Metric.WATER_TEMP, 22.0, "°C"),
                ],
                advisory=Advisory(kind=AdvisoryKind.NONE, source="테스트"),
                forecast=forecast,
            )
        },
    )


def _clean_llm(system, user):
    return "무난한 조건입니다."


def test_safe_window_for_deterministic():
    now = datetime(2026, 7, 12, 9, 0, 0)
    fc = [ForecastPoint(time=now + timedelta(hours=1), wave_height=0.5, wind_speed=5.0)]
    w = safe_window_for(get_spot("haeundae"), LEISURE, doc=_full_doc(fc), now=now)
    assert w is not None
    assert w.grade is Grade.SAFE


def test_safe_window_none_without_forecast():
    assert safe_window_for(get_spot("haeundae"), LEISURE, doc=_full_doc([])) is None


def test_brief_spot_includes_safe_window():
    # 실제 now 기준 미래 시각(테스트 실행 시점 +1/+2h)이라 항상 지평 내 미래.
    now = datetime.now(_KST).replace(tzinfo=None)
    fc = [
        ForecastPoint(time=now + timedelta(hours=1), wave_height=0.5, wind_speed=5.0),
        ForecastPoint(time=now + timedelta(hours=2), wave_height=0.5, wind_speed=5.0),
    ]
    b = brief_spot(get_spot("haeundae"), LEISURE, doc=_full_doc(fc), llm_fn=_clean_llm)
    assert b.safe_window is not None
    assert b.safe_window.grade is Grade.SAFE


def test_snapshot_roundtrip_preserves_forecast():
    fc = [ForecastPoint(time=_AS_OF, wave_height=0.5, wind_speed=5.0)]
    doc = _full_doc(fc)
    reloaded = SnapshotDoc.model_validate(json.loads(doc.model_dump_json()))
    snap = reloaded.spot("haeundae")
    assert len(snap.forecast) == 1
    assert snap.forecast[0].wave_height == 0.5
