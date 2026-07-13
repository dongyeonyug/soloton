"""E1 가드 시연 — 판정이 하드코딩이 아니라 프로덕션 가드 실행 결과임을 고정한다.

시연의 설득력은 "실제 코드가 돌았다"에 전부 걸려 있으므로, 여기서는 시나리오별 기대
문구가 아니라 **불변식**을 검증한다: 위반이 있으면 반드시 폐기되고, 서빙되는 문장은
어떤 경우에도 숫자가 없다.
"""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from app.briefing import guard
from app.briefing.demo import check_prose, run_demo
from app.ingest.cache import SnapshotDoc, SpotSnapshot
from app.main import app
from app.models import Advisory, AdvisoryKind, MarineObservation, Metric
from app.spots import get_spot

client = TestClient(app)

AS_OF = datetime(2026, 7, 12, 1, 0, 0)
SPOT_ID = "haeundae"


def _obs(metric: Metric, value: float, unit: str) -> MarineObservation:
    return MarineObservation(
        spot_id=SPOT_ID,
        metric=metric,
        value=value,
        unit=unit,
        observed_at=AS_OF,
        source="테스트",
    )


def _doc() -> SnapshotDoc:
    return SnapshotDoc(
        snapshot_as_of=AS_OF,
        source="test",
        spots={
            SPOT_ID: SpotSnapshot(
                observations=[
                    _obs(Metric.WAVE_HEIGHT, 0.4, "m"),
                    _obs(Metric.WIND_SPEED, 3.2, "m/s"),
                    _obs(Metric.CURRENT_SPEED, 0.2, "m/s"),
                    _obs(Metric.TIDE_LEVEL, 123.0, "cm"),
                    _obs(Metric.WATER_TEMP, 22.0, "°C"),
                ],
                advisory=Advisory(kind=AdvisoryKind.NONE, source="테스트"),
            )
        },
    )


def _spot():
    return get_spot(SPOT_ID)


def test_invented_numbers_are_blocked():
    """수치를 지어낸 산문은 폐기되고, 대신 코드 생성 폴백이 서빙된다."""
    v = check_prose(_spot(), "파고 0.5m로 잔잔하고 바람도 초속 4m 수준입니다.", doc=_doc())
    assert v.blocked is True
    assert v.llm_used is False
    assert v.served_prose != v.text
    assert guard.is_number_free(v.served_prose)


def test_invented_time_is_blocked():
    """한글 시각(T3-a 가드)도 같은 경로에서 폐기된다."""
    v = check_prose(_spot(), "오후 세 시쯤이면 물결이 잦아듭니다.", doc=_doc())
    assert v.blocked is True
    assert v.llm_used is False
    assert guard.is_number_free(v.served_prose)


def test_number_free_prose_is_served_as_is():
    """숫자 없는 산문은 원문 그대로 서빙된다(가드는 표현을 검열하지 않는다)."""
    text = "지금은 활동하기에 무난한 편입니다. 상황을 살피며 여유를 두세요."
    v = check_prose(_spot(), text, doc=_doc())
    assert v.blocked is False
    assert v.violations == []
    assert v.llm_used is True
    assert v.served_prose == text


def test_violation_spans_point_at_the_real_tokens():
    """스팬은 원문 오프셋과 정확히 일치한다(프론트 하이라이트가 엉뚱한 글자를 칠하지 않도록)."""
    text = "파고는 1.5미터, 바람은 오후 두 시부터 강해집니다."
    v = check_prose(_spot(), text, doc=_doc())
    assert v.violations == [text[s:e] for s, e in v.violation_spans]
    assert "오후 두 시" in v.violations


def test_distinct_violations_are_not_merged_into_one():
    """맞닿은 서로 다른 위반은 따로 센다 — 화면의 '위반 N건'이 실제보다 줄면 안 된다."""
    assert guard.find_number_violations("오후 두 시3미터") == ["오후 두 시", "3"]
    # 규칙이 같은 글자를 겹쳐 잡은 경우만 한 토큰
    assert guard.find_number_violations("1.5") == ["1.5"]
    assert guard.find_number_violations("１．５") == ["１．５"]


def test_blocked_is_derived_from_production_outcome():
    """회귀: 폐기 여부는 시연이 따로 판단하지 않고 프로덕션 결과(llm_used)에서 나온다."""
    text = "숫자 없는 정상 문장입니다."
    assert guard.is_number_free(text)
    v = check_prose(_spot(), text, doc=_doc())
    assert v.blocked is not v.llm_used


def test_demo_runs_every_scenario_through_the_real_guard():
    """시연 전체 불변식: 위반 있으면 폐기, 서빙 문장은 언제나 숫자 0개."""
    demo = run_demo(_spot(), doc=_doc())
    assert len(demo.cases) >= 4
    assert any(c.blocked for c in demo.cases)
    assert any(not c.blocked for c in demo.cases)

    for case in demo.cases:
        assert case.blocked == bool(case.violations)
        assert case.blocked != case.llm_used  # 폐기 ⇔ AI 문장 미사용
        assert guard.is_number_free(case.served_prose)


def test_demo_endpoint():
    r = client.get("/api/guard/demo")
    assert r.status_code == 200
    body = r.json()
    assert body["spot_id"] == SPOT_ID
    assert any(c["blocked"] for c in body["cases"])


def test_check_endpoint_blocks_user_supplied_numbers():
    r = client.get("/api/guard/check", params={"text": "파고는 2미터입니다."})
    assert r.status_code == 200
    body = r.json()
    assert body["blocked"] is True
    assert body["llm_used"] is False
    assert body["served_prose"] != body["text"]


def test_check_endpoint_rejects_empty_and_overlong_text():
    assert client.get("/api/guard/check", params={"text": ""}).status_code == 422
    assert client.get("/api/guard/check", params={"text": "   "}).status_code == 422
    assert client.get("/api/guard/check", params={"text": "바" * 301}).status_code == 422


def test_demo_unknown_spot_404():
    assert client.get("/api/guard/demo", params={"spot_id": "nope"}).status_code == 404
