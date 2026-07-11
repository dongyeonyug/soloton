"""AC3: 골드 케이스 (파고,풍속,특보,활동)→기대등급 100% 일치."""

import pytest

from app.engine.risk import evaluate
from app.models import Grade

from .helpers import build_inputs, load_gold_cases

CASES = load_gold_cases()


def test_gold_case_count():
    # 등급 경계·활동별 충분한 케이스 보장
    assert len(CASES) >= 20


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_gold_case(case):
    observations, advisory, activity = build_inputs(case)
    result = evaluate(observations, advisory, activity, time_slot="09-12")
    assert result.grade == Grade(case["expected"]), (
        f"{case['id']}: expected {case['expected']}, got {result.grade.value}"
    )
