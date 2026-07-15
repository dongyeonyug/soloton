"""T11: 최근 공식 특보 레코드가 위험도 하한으로 재현되는지 검증한다.

여기서 파고·풍속은 특보 override를 고립하기 위한 합성 제어 입력이다. 실제 당시
해상 상태나 사고 결과를 재현한다고 주장하지 않는다.
"""

import pytest

from app.engine.risk import evaluate
from app.models import Grade, RuleEvidence

from .helpers import build_inputs, load_advisory_replay_cases

SOURCE, CASES = load_advisory_replay_cases()


def test_advisory_replay_has_official_provenance_and_limited_scope():
    assert SOURCE["data_id"] == "15000415"
    assert SOURCE["operation"] == "getWthrWrnList"
    assert "장기 특보 아카이브가 아니다" in SOURCE["retention_note"]
    assert all(case["numeric_input_kind"] == "synthetic_control" for case in CASES)


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_recent_official_advisory_records_replay_to_expected_grade_floor(case):
    observations, advisory = build_inputs(case)
    result = evaluate(observations, advisory, "특보 재현")

    assert case["advisory"] in case["source_record"]["title"]
    assert result.grade is Grade(case["expected_grade"])
    advisory_step = next(step for step in result.decision_steps if step.label == "기상특보")
    assert advisory_step.result_grade is result.grade
    assert advisory_step.rule_evidence is RuleEvidence.OFFICIAL_BASELINE
