"""AC2: 규칙 엔진 결정론 — 동일 입력 → 동일 등급 (시계·난수 無)."""

import pytest

from app.engine.risk import evaluate
from app.models import Grade

from .helpers import build_inputs, load_gold_cases

CASES = load_gold_cases()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_determinism_repeat(case):
    observations, advisory, activity = build_inputs(case)
    first = evaluate(observations, advisory, activity, "09-12")
    second = evaluate(observations, advisory, activity, "09-12")
    assert first.grade == second.grade
    assert first.has_missing_critical == second.has_missing_critical


def test_worst_of_semantics():
    """등급 = 기여 지표 worst."""
    case = {"wave": 3.5, "wind": 5.0, "current": 0.2, "advisory": "none", "activity": "조업"}
    obs, adv, act = build_inputs(case)
    assert evaluate(obs, adv, act, "09-12").grade == Grade.DANGER


def test_advisory_never_downgrades():
    """활성 특보는 자기 등급 이상으로만 override — 데이터가 더 위험하면 유지."""
    case = {"wave": 3.5, "wind": 5.0, "current": 0.2, "advisory": "풍랑주의보", "activity": "조업"}
    obs, adv, act = build_inputs(case)
    # 데이터=DANGER, 특보=CAUTION → DANGER 유지 (다운그레이드 없음)
    assert evaluate(obs, adv, act, "09-12").grade == Grade.DANGER


def test_no_clock_or_random_import():
    """risk.py 소스에 time/random 직접 사용 없음(정적 가드)."""
    import inspect

    import app.engine.risk as risk_mod

    src = inspect.getsource(risk_mod)
    assert "random" not in src
    assert "datetime.now" not in src
    assert "time.time" not in src
