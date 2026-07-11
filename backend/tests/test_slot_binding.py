"""AC4: 속성-바인딩 검증 — 각 수치 슬롯이 라벨된 basis_value 에만 바인딩.

파고 자리에 풍속값이 들어가는 오결합이 0건임을 구조적으로 대조한다.
"""

import pytest

from app.engine.thresholds import THRESHOLDS
from app.models import Activity, Metric
from app.service import evaluate_spot
from app.briefing.template import build_slots
from app.spots import all_spots

# metric → 정규 라벨 (사실의 원천)
CANON_LABEL = {m: band.label for m, band in THRESHOLDS.items()}

ACTIVITIES = list(Activity)


@pytest.mark.parametrize("spot", all_spots(), ids=[s.id for s in all_spots()])
def test_slot_label_matches_metric(spot):
    for activity in ACTIVITIES:
        risk, as_of = evaluate_spot(spot, activity)
        slots = build_slots(spot, risk, as_of)

        # basis_value 의 metric↔label 이 정규 라벨과 일치
        for bv in risk.basis_values:
            if bv.metric in CANON_LABEL:
                assert bv.label == CANON_LABEL[bv.metric], (
                    f"{spot.id}/{activity.value}: {bv.metric} 라벨 오결합 {bv.label}"
                )

        # FilledNumber 는 basis_value 로부터만 파생 (값·라벨 쌍 보존)
        pairs_risk = [(bv.label, bv.value) for bv in risk.basis_values]
        pairs_slot = [(f.label, f.value) for f in slots.filled_numbers]
        assert pairs_slot == pairs_risk, f"{spot.id}/{activity.value}: 슬롯-바인딩 불일치"


def test_no_cross_metric_value_leak():
    """풍속값이 파고 라벨 슬롯에 절대 들어가지 않음(값 출처 대조)."""
    for spot in all_spots():
        risk, as_of = evaluate_spot(spot, Activity.FISHING)
        slots = build_slots(spot, risk, as_of)
        by_label = {f.label: f for f in slots.filled_numbers}
        wave = by_label.get(CANON_LABEL[Metric.WAVE_HEIGHT])
        wind = by_label.get(CANON_LABEL[Metric.WIND_SPEED])
        # 두 슬롯이 모두 present 면 서로 다른 unit(m vs m/s)로 출처 구분됨
        if wave and wind and not wave.is_missing and not wind.is_missing:
            assert wave.unit == "m"
            assert wind.unit == "m/s"
