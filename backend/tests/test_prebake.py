"""T1 프리-베이크: 크론이 기본 활동 산문을 미리 생성해 스냅샷에 저장하고,
서빙은 저장 산문을 (가드 재통과 후) 즉시 서빙한다. AI 를 요청 경로에서 제거.

이중 게이트 불변식: 저장 산문이라도 서빙 시 런타임 가드를 다시 통과해야만 쓰인다.
"""

from __future__ import annotations

import json
from datetime import datetime

from app.ingest.cache import SnapshotDoc, SpotSnapshot
from app.ingest.collect import bake_briefings
from app.models import Activity, Advisory, AdvisoryKind, MarineObservation, Metric
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
    """가드 통과 산문은 스냅샷에 저장된다(llm_used=True)."""
    doc = _doc()
    bake_briefings(doc, llm_fn=_clean_llm)
    snap = doc.spot(SPOT_ID)
    assert snap.llm_used is True
    assert snap.llm_prose == _clean_llm(None, None)


def test_bake_skips_numbery_prose():
    """숫자 낀 산문은 가드에 걸려 저장되지 않는다(None 유지)."""
    doc = _doc()
    bake_briefings(doc, llm_fn=_numbery_llm)
    snap = doc.spot(SPOT_ID)
    assert snap.llm_used is False
    assert snap.llm_prose is None


def test_serve_uses_baked_prose_for_default_activity():
    """기본 경로(레저·현재, 주입 LLM 없음)는 저장 산문을 그대로 서빙한다."""
    doc = _doc()
    doc.spot(SPOT_ID).llm_prose = "안전하게 여유를 갖고 활동하세요."
    doc.spot(SPOT_ID).llm_used = True

    briefing = brief_spot(get_spot(SPOT_ID), Activity.LEISURE, doc=doc)
    assert briefing.llm_used is True
    assert briefing.llm_prose == "안전하게 여유를 갖고 활동하세요."


def test_serve_ignores_bake_for_nondefault_activity(monkeypatch):
    """비기본 활동은 레저용으로 구운 산문을 재사용하지 않는다.

    라이브 경로를 결정론적으로 만들기 위해 _default_llm 을 비활성화(키 유무와 무관하게
    실제 API 호출 없음). 핵심 불변식은 'FISHING 은 LEISURE 베이크를 안 쓴다'.
    """
    monkeypatch.setattr("app.briefing.generate._default_llm", lambda: None)
    doc = _doc()
    doc.spot(SPOT_ID).llm_prose = "레저용으로 구워둔 산문"
    doc.spot(SPOT_ID).llm_used = True

    briefing = brief_spot(get_spot(SPOT_ID), Activity.FISHING, doc=doc)
    assert briefing.llm_prose != "레저용으로 구워둔 산문"
    assert briefing.llm_used is False


def test_baked_prose_is_reguarded_at_serve_time():
    """회귀: 저장 산문에 숫자가 있으면 서빙 시 가드가 폐기하고 폴백한다(이중 게이트)."""
    doc = _doc()
    doc.spot(SPOT_ID).llm_prose = "파고 3미터라 위험합니다."  # 오염된 저장분
    doc.spot(SPOT_ID).llm_used = True

    briefing = brief_spot(get_spot(SPOT_ID), Activity.LEISURE, doc=doc)
    assert briefing.llm_used is False
    assert briefing.llm_prose != "파고 3미터라 위험합니다."


def test_snapshot_roundtrip_preserves_baked_prose():
    """직렬화 라운드트립에서 저장 산문·플래그가 보존된다."""
    doc = _doc()
    doc.spot(SPOT_ID).llm_prose = "무난한 조건입니다."
    doc.spot(SPOT_ID).llm_used = True

    reloaded = SnapshotDoc.model_validate(json.loads(doc.model_dump_json()))
    snap = reloaded.spot(SPOT_ID)
    assert snap.llm_prose == "무난한 조건입니다."
    assert snap.llm_used is True
