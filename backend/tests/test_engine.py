"""AC2: 규칙 엔진 결정론 — 동일 입력 → 동일 등급 (시계·난수 無)."""

import pytest

from app.engine.risk import evaluate
from app.models import Grade, Metric, RuleEvidence

from .helpers import build_inputs, load_gold_cases

CASES = load_gold_cases()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_determinism_repeat(case):
    observations, advisory = build_inputs(case)
    first = evaluate(observations, advisory, "09-12")
    second = evaluate(observations, advisory, "09-12")
    assert first.grade == second.grade
    assert first.has_missing_critical == second.has_missing_critical


def test_worst_of_semantics():
    """등급 = 기여 지표 worst."""
    case = {"wave": 3.5, "wind": 5.0, "current": 0.2, "advisory": "none"}
    obs, adv = build_inputs(case)
    assert evaluate(obs, adv, "09-12").grade == Grade.DANGER


def test_advisory_never_downgrades():
    """활성 특보는 자기 등급 이상으로만 override — 데이터가 더 위험하면 유지."""
    case = {"wave": 3.5, "wind": 5.0, "current": 0.2, "advisory": "풍랑주의보"}
    obs, adv = build_inputs(case)
    # 데이터=DANGER, 특보=CAUTION → DANGER 유지 (다운그레이드 없음)
    assert evaluate(obs, adv, "09-12").grade == Grade.DANGER


def test_no_clock_or_random_import():
    """risk.py 소스에 time/random 직접 사용 없음(정적 가드)."""
    import inspect

    import app.engine.risk as risk_mod

    src = inspect.getsource(risk_mod)
    assert "random" not in src
    assert "datetime.now" not in src
    assert "time.time" not in src


def test_decision_steps_record_metric_results_and_final_grade():
    """T5: 최종 등급 이전의 코드 판단 경로가 API에 남는다."""
    obs, adv = build_inputs(
        {"wave": 2.5, "wind": 5.0, "current": 0.2, "advisory": "none"}
    )
    result = evaluate(obs, adv, "09-12")

    wave = next(step for step in result.decision_steps if step.label == "유의파고")
    assert wave.result_grade is Grade.CAUTION
    assert wave.rule_evidence is RuleEvidence.CONSERVATIVE_MAPPING
    assert result.decision_steps[-1].label == "최종 위험도"
    assert result.decision_steps[-1].result_grade is result.grade

    wave_basis = next(
        value for value in result.basis_values if value.metric is Metric.WAVE_HEIGHT
    )
    assert wave_basis.rule_evidence is RuleEvidence.CONSERVATIVE_MAPPING


def test_current_speed_is_visible_but_cannot_change_the_grade():
    obs, adv = build_inputs(
        {"wave": 0.5, "wind": 5.0, "current": 2.5, "advisory": "none"}
    )
    result = evaluate(obs, adv, "09-12")

    assert result.grade is Grade.SAFE
    current = next(value for value in result.basis_values if value.metric is Metric.CURRENT_SPEED)
    assert current.is_reference is True
    assert "등급에 반영하지 않음" in current.reference_note
    current_step = next(step for step in result.decision_steps if step.label == "조류")
    assert current_step.result_grade is None
