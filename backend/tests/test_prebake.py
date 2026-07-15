"""프리-베이크: 크론이 기본 현재 브리핑 산문을 미리 생성해 스냅샷에 저장하고,
서빙은 저장 산문을 (가드 재통과 후) 즉시 서빙한다. AI 를 요청 경로에서 제거.

이중 게이트 불변식: 저장 산문이라도 서빙 시 런타임 가드를 다시 통과해야만 쓰인다.
"""

from __future__ import annotations

import json
import time
from datetime import datetime

from app.ingest.cache import SNAPSHOT_SCHEMA_VERSION, SnapshotDoc, SpotSnapshot
from app.ingest.collect import bake_briefings
from app.models import Advisory, AdvisoryKind, MarineObservation, Metric, ProseStatus
from app.service import brief_spot
from app.spots import get_spot

AS_OF = datetime(2026, 7, 12, 1, 0, 0)
SPOT_ID = "haeundae"


def _clean_llm(system, user):
    return "현재 여건은 무난한 편입니다. 안전 수칙을 지키며 여유롭게 활동하세요."


def _numbery_llm(system, user):
    # 가드가 반드시 폐기해야 하는 산문(아라비아 숫자 포함).
    return "파고 3미터로 매우 위험합니다."


def _obs(metric: Metric, value: float | None, unit: str) -> MarineObservation:
    return MarineObservation(
        spot_id=SPOT_ID,
        metric=metric,
        value=value,
        unit=unit,
        observed_at=AS_OF if value is not None else None,
        source="테스트",
        is_missing=value is None,
    )


def _doc() -> SnapshotDoc:
    return SnapshotDoc(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
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


def test_bake_stores_guard_passed_prose():
    """가드 통과 산문만 verified 상태로 스냅샷에 저장된다."""
    doc = _doc()
    bake_briefings(doc, llm_fn=_clean_llm)
    snap = doc.spot(SPOT_ID)
    assert snap.prose_status == ProseStatus.VERIFIED
    assert snap.llm_prose == _clean_llm(None, None)


def test_bake_skips_numbery_prose():
    """숫자 낀 산문은 가드에 걸려 저장되지 않는다(None 유지)."""
    doc = _doc()
    bake_briefings(doc, llm_fn=_numbery_llm)
    snap = doc.spot(SPOT_ID)
    assert snap.prose_status == ProseStatus.BLOCKED_BY_GUARD
    assert snap.llm_prose is None


def test_serve_uses_baked_prose_for_default_briefing():
    """기본 현재 브리핑은 저장 산문을 그대로 서빙한다."""
    doc = _doc()
    doc.spot(SPOT_ID).llm_prose = "안전하게 여유를 갖고 활동하세요."
    doc.spot(SPOT_ID).prose_status = ProseStatus.VERIFIED

    briefing = brief_spot(get_spot(SPOT_ID), doc=doc)
    assert briefing.prose_status == ProseStatus.VERIFIED
    assert briefing.llm_prose == "안전하게 여유를 갖고 활동하세요."


def test_serve_uses_one_bake_for_the_single_coastal_context():
    """활동별 분기 없이 하나의 저장 산문을 해안 활동 참고에 사용한다."""
    doc = _doc()
    doc.spot(SPOT_ID).llm_prose = "해안 여건을 확인하고 여유 있게 움직이세요."
    doc.spot(SPOT_ID).prose_status = ProseStatus.VERIFIED

    briefing = brief_spot(get_spot(SPOT_ID), doc=doc)
    assert briefing.llm_prose == "해안 여건을 확인하고 여유 있게 움직이세요."
    assert briefing.prose_status == ProseStatus.VERIFIED


def test_serve_without_baked_prose_never_calls_default_llm(monkeypatch):
    """구 스냅샷을 비워도 공개 요청은 코드 폴백으로 끝난다."""
    def fail_if_called():
        raise AssertionError("public briefing must not call the default LLM")

    monkeypatch.setattr("app.briefing.generate._default_llm", fail_if_called)
    briefing = brief_spot(get_spot(SPOT_ID), doc=_doc())

    assert briefing.prose_status == ProseStatus.GENERATION_UNAVAILABLE


def test_baked_prose_is_reguarded_at_serve_time():
    """회귀: 저장 산문에 숫자가 있으면 서빙 시 가드가 폐기하고 폴백한다(이중 게이트)."""
    doc = _doc()
    doc.spot(SPOT_ID).llm_prose = "파고 3미터라 위험합니다."  # 오염된 저장분
    doc.spot(SPOT_ID).prose_status = ProseStatus.VERIFIED

    briefing = brief_spot(get_spot(SPOT_ID), doc=doc)
    assert briefing.prose_status == ProseStatus.BLOCKED_BY_GUARD
    assert briefing.llm_prose != "파고 3미터라 위험합니다."


def test_legacy_snapshot_prose_is_not_served():
    """v1 스냅샷은 산문이 있어도 코드 폴백만 반환한다."""
    doc = _doc()
    doc.schema_version = 1
    doc.spot(SPOT_ID).llm_prose = "구 버전 산문은 재사용하면 안 됩니다."
    doc.spot(SPOT_ID).prose_status = ProseStatus.VERIFIED

    briefing = brief_spot(get_spot(SPOT_ID), doc=doc)
    assert briefing.prose_status == ProseStatus.DETERMINISTIC_FALLBACK
    assert briefing.llm_prose != "구 버전 산문은 재사용하면 안 됩니다."


def test_nonverified_snapshot_prose_is_not_served():
    """v2라도 verified 가 아닌 산문은 신뢰하지 않고 상태에 맞는 폴백을 쓴다."""
    doc = _doc()
    doc.spot(SPOT_ID).llm_prose = "생성 실패인데 남아 있던 산문입니다."
    doc.spot(SPOT_ID).prose_status = ProseStatus.GENERATION_UNAVAILABLE

    briefing = brief_spot(get_spot(SPOT_ID), doc=doc)
    assert briefing.prose_status == ProseStatus.GENERATION_UNAVAILABLE
    assert briefing.llm_prose != "생성 실패인데 남아 있던 산문입니다."


def test_snapshot_roundtrip_preserves_prose_status():
    """직렬화 라운드트립에서 저장 산문·상태·스키마 버전이 보존된다."""
    doc = _doc()
    doc.spot(SPOT_ID).llm_prose = "무난한 조건입니다."
    doc.spot(SPOT_ID).prose_status = ProseStatus.VERIFIED

    reloaded = SnapshotDoc.model_validate(json.loads(doc.model_dump_json()))
    snap = reloaded.spot(SPOT_ID)
    assert reloaded.schema_version == SNAPSHOT_SCHEMA_VERSION
    assert snap.llm_prose == "무난한 조건입니다."
    assert snap.prose_status == ProseStatus.VERIFIED


def test_bake_records_generation_unavailable_per_spot():
    """한 지점의 생성 실패는 전체 배치를 중단하지 않고 상태로 남긴다."""
    doc = _doc()

    def unavailable_llm(_system, _user):
        raise TimeoutError("provider timeout")

    bake_briefings(doc, llm_fn=unavailable_llm)
    snap = doc.spot(SPOT_ID)
    assert snap.llm_prose is None
    assert snap.prose_status == ProseStatus.GENERATION_UNAVAILABLE


def test_bake_records_timeout_without_blocking_the_batch():
    """지점별 제한 시간을 넘긴 생성은 기다리지 않고 generation_unavailable 로 남긴다."""
    doc = _doc()

    def slow_llm(_system, _user):
        time.sleep(0.05)
        return _clean_llm(None, None)

    bake_briefings(doc, llm_fn=slow_llm, timeout_seconds=0.001)
    snap = doc.spot(SPOT_ID)
    assert snap.llm_prose is None
    assert snap.prose_status == ProseStatus.GENERATION_UNAVAILABLE
