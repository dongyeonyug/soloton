"""AC5b: 자백(브리핑) — 결측 주입 → is_confession=true, 결측 지표 수치 주장 없음."""

from datetime import datetime

from app.briefing.template import MISSING_TEXT, build_slots, render_template
from app.ingest.cache import SnapshotDoc, SpotSnapshot
from app.models import Advisory, AdvisoryKind, MarineObservation, Metric
from app.service import brief_spot, evaluate_spot
from app.spots import get_spot

AS_OF = datetime(2026, 7, 12, 1, 0, 0)


def _fake_llm_clean(system, user):
    return "현재 여건을 신중히 살피고 안전 수칙을 지키세요."


def _obs(metric: Metric, value: float | None, unit: str) -> MarineObservation:
    return MarineObservation(
        spot_id="cheongsapo",
        metric=metric,
        value=value,
        unit=unit,
        observed_at=AS_OF if value is not None else None,
        source="테스트",
        is_missing=value is None,
    )


def _doc(*, missing_wind: bool) -> SnapshotDoc:
    wind = None if missing_wind else 3.2
    return SnapshotDoc(
        snapshot_as_of=AS_OF,
        source="test",
        spots={
            "cheongsapo": SpotSnapshot(
                observations=[
                    _obs(Metric.WAVE_HEIGHT, 0.4, "m"),
                    _obs(Metric.WIND_SPEED, wind, "m/s"),
                    _obs(Metric.CURRENT_SPEED, 0.2, "m/s"),
                    _obs(Metric.TIDE_LEVEL, 123.0, "cm"),
                    _obs(Metric.WATER_TEMP, 22.0, "°C"),
                ],
                advisory=Advisory(kind=AdvisoryKind.NONE, source="테스트"),
            )
        },
    )


def test_missing_spot_confesses():
    spot = get_spot("cheongsapo")
    briefing = brief_spot(spot, doc=_doc(missing_wind=True), llm_fn=_fake_llm_clean)
    assert briefing.is_confession is True


def test_missing_metric_shows_infoless_not_number():
    spot = get_spot("cheongsapo")
    risk, as_of = evaluate_spot(spot, doc=_doc(missing_wind=True))
    slots = build_slots(spot, risk, as_of)
    text = render_template(spot, risk, slots)
    # 결측 풍속은 '정보없음' 으로 자백, 조작된 수치 없음
    wind_slot = next(f for f in slots.filled_numbers if f.label == "풍속")
    assert wind_slot.is_missing is True
    assert wind_slot.value is None
    assert f"풍속 {MISSING_TEXT}" in text


def test_template_displays_snapshot_time_in_kst():
    spot = get_spot("cheongsapo")
    risk, as_of = evaluate_spot(spot, doc=_doc(missing_wind=False))
    slots = build_slots(spot, risk, as_of)
    text = render_template(spot, risk, slots)

    assert "기준 시각 2026-07-12 10:00" in text


def test_present_spot_not_confession():
    spot = get_spot("cheongsapo")
    briefing = brief_spot(spot, doc=_doc(missing_wind=False), llm_fn=_fake_llm_clean)
    assert briefing.is_confession is False
