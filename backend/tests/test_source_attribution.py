"""P0 회귀 — 출처 표기 배관: 관측 출처(실측/예보)가 화면 인용까지 보존된다.

과거 결함: engine/risk.py 가 BasisValue.source 를 임계 밴드 텍스트로 덮어써
관측 출처(KHOA 실측 vs Open-Meteo 예보 백필)가 프론트에 도달하지 못했고,
'출처:' 라벨이 실제로는 판단 기준을 가리켰다. 이 파일은 그 배관을 고정한다.
"""

from __future__ import annotations

from datetime import datetime

from app.briefing.template import build_slots, observed_kind, render_template
from app.engine.risk import evaluate
from app.engine.thresholds import THRESHOLDS
from app.models import (
    Advisory,
    AdvisoryKind,
    DataStatus,
    Grade,
    MarineObservation,
    Metric,
    RuleEvidence,
)
from app.spots import all_spots

FIXED_TIME = datetime(2026, 7, 10, 9, 0, 0)
KHOA_WAVE = "KHOA 바다누리(실측)"
KHOA_WIND = "KHOA 해양관측부이(실측)"
OM_WAVE = "Open-Meteo 해양모델(MFWAM/ECMWF)"
OM_WIND = "Open-Meteo 기상모델"
KHOA_TIDE = "KHOA 조위관측소(실측)"


def _obs(metric: Metric, value: float | None, unit: str, source: str) -> MarineObservation:
    return MarineObservation(
        spot_id="test",
        metric=metric,
        value=value,
        unit=unit,
        observed_at=None if value is None else FIXED_TIME,
        source=source,
        is_missing=value is None,
    )


def _advisory() -> Advisory:
    return Advisory(kind=AdvisoryKind.NONE, source="기상청 특보")


def _brief(observations):
    risk = evaluate(observations, _advisory(), "현재")
    spot = all_spots()[0]
    slots = build_slots(spot, risk, FIXED_TIME)
    return risk, slots, render_template(spot, risk, slots)


def _by_label(slots):
    return {f.label: f for f in slots.filled_numbers}


def test_observed_source_flows_to_citation_and_differs_by_origin():
    """실측 지점과 예보 백필 지점의 citation 관측 출처가 달라야 한다."""
    measured = {
        Metric.WAVE_HEIGHT: _obs(Metric.WAVE_HEIGHT, 0.5, "m", KHOA_WAVE),
        Metric.WIND_SPEED: _obs(Metric.WIND_SPEED, 5.0, "m/s", KHOA_WIND),
    }
    backfilled = {
        Metric.WAVE_HEIGHT: _obs(Metric.WAVE_HEIGHT, 0.5, "m", OM_WAVE),
        Metric.WIND_SPEED: _obs(Metric.WIND_SPEED, 5.0, "m/s", OM_WIND),
    }
    _, slots_m, _ = _brief(measured)
    _, slots_b, _ = _brief(backfilled)
    wave_label = THRESHOLDS[Metric.WAVE_HEIGHT].label

    wave_m = _by_label(slots_m)[wave_label]
    wave_b = _by_label(slots_b)[wave_label]
    assert wave_m.observed_source == KHOA_WAVE
    assert wave_b.observed_source == OM_WAVE
    assert wave_m.observed_source != wave_b.observed_source
    assert wave_m.observed_kind == "실측"
    assert wave_b.observed_kind == "예보"
    assert wave_m.data_status is DataStatus.OBSERVED
    assert wave_b.data_status is DataStatus.FORECAST
    assert wave_m.is_critical is True


def test_criterion_is_band_not_source():
    """판단 기준(임계 밴드)은 criterion 으로 분리 보존, 관측 출처와 섞이지 않는다."""
    observations = {
        Metric.WAVE_HEIGHT: _obs(Metric.WAVE_HEIGHT, 0.5, "m", KHOA_WAVE),
        Metric.WIND_SPEED: _obs(Metric.WIND_SPEED, 5.0, "m/s", KHOA_WIND),
    }
    _, slots, template = _brief(observations)
    wave = _by_label(slots)[THRESHOLDS[Metric.WAVE_HEIGHT].label]
    assert wave.criterion == THRESHOLDS[Metric.WAVE_HEIGHT].source
    assert "실측" not in wave.criterion
    # 템플릿 산문에서 '출처:'는 관측 출처를, '판단 기준:'은 밴드를 가리킨다
    assert f"출처: {KHOA_WAVE} / 판단 기준:" in template
    assert wave.rule_evidence is RuleEvidence.CONSERVATIVE_MAPPING


def test_missing_value_claims_no_source():
    """결측 지표는 출처를 주장하지 않는다(관측된 적 없는 값에 실측 라벨 금지)."""
    observations = {
        Metric.WAVE_HEIGHT: _obs(Metric.WAVE_HEIGHT, None, "m", KHOA_WAVE),
        Metric.WIND_SPEED: _obs(Metric.WIND_SPEED, 5.0, "m/s", KHOA_WIND),
    }
    _, slots, _ = _brief(observations)
    wave = _by_label(slots)[THRESHOLDS[Metric.WAVE_HEIGHT].label]
    assert wave.is_missing
    assert wave.observed_source == ""
    assert wave.observed_kind == ""
    assert wave.checked_source == KHOA_WAVE
    assert wave.data_status is DataStatus.MISSING
    assert wave.is_critical is True


def test_tide_reference_citation_present_and_grade_neutral():
    """조위는 참고 지표로 citation 에 나타나되 등급·자백에 영향 없다."""
    base = {
        Metric.WAVE_HEIGHT: _obs(Metric.WAVE_HEIGHT, 0.5, "m", KHOA_WAVE),
        Metric.WIND_SPEED: _obs(Metric.WIND_SPEED, 5.0, "m/s", KHOA_WIND),
        Metric.CURRENT_SPEED: _obs(Metric.CURRENT_SPEED, 0.3, "m/s", OM_WAVE),
    }
    # 조위 결측: '정보없음' 칩으로 자백하되 confession/등급 불변
    risk_missing, slots_missing, _ = _brief(dict(base))
    tide = _by_label(slots_missing)["조위"]
    assert tide.is_reference and tide.is_missing
    assert tide.checked_source == ""
    assert tide.is_critical is False
    assert risk_missing.grade is Grade.SAFE
    assert not slots_missing.is_confession
    assert not risk_missing.has_missing_critical

    # 조위 극단값이 있어도 등급은 그대로(비임계)
    with_tide = dict(base)
    with_tide[Metric.TIDE_LEVEL] = _obs(Metric.TIDE_LEVEL, 999.0, "cm", KHOA_TIDE)
    risk_tide, slots_tide, template = _brief(with_tide)
    tide2 = _by_label(slots_tide)["조위"]
    assert risk_tide.grade is Grade.SAFE
    assert tide2.value == 999.0
    assert tide2.observed_source == KHOA_TIDE
    assert tide2.criterion == ""
    assert tide2.data_status is DataStatus.OBSERVED
    assert "등급 비반영 참고값" in template


def test_observed_kind_classifier():
    assert observed_kind(KHOA_WAVE) == "실측"
    assert observed_kind(OM_WIND) == "예보"
    assert observed_kind("") == ""
    assert observed_kind("공공 해양데이터") == ""
