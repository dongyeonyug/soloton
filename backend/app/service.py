"""파이프라인 조립 — 스냅샷 → 신선도 → 등급 → 브리핑. 라우터·테스트 공용.

C1 해소: 커밋 스냅샷 경로에서는 신선도 만료를 snapshot_as_of 기준으로 판정한다
(데모가 전부 '정보없음'으로 무너지지 않도록).
"""

from __future__ import annotations

from datetime import datetime

from .briefing.generate import LLMFn, generate_briefing
from .engine.risk import evaluate, mark_stale
from .ingest.cache import SnapshotDoc, get_snapshot
from .models import Activity, Briefing, RiskGrade
from .spots import Spot, get_spot

DEFAULT_TIME_SLOT = "현재"


def evaluate_spot(
    spot: Spot,
    activity: Activity,
    *,
    doc: SnapshotDoc | None = None,
    time_slot: str = DEFAULT_TIME_SLOT,
) -> tuple[RiskGrade, datetime]:
    doc = doc or get_snapshot()
    snap = doc.spot(spot.id)
    if snap is None:
        raise KeyError(spot.id)
    as_of = doc.snapshot_as_of
    obs, adv = mark_stale(snap.as_map(), snap.advisory, as_of=as_of)
    risk = evaluate(obs, adv, activity, time_slot)
    return risk, as_of


def brief_spot(
    spot: Spot,
    activity: Activity,
    *,
    doc: SnapshotDoc | None = None,
    time_slot: str = DEFAULT_TIME_SLOT,
    llm_fn: LLMFn | None = None,
) -> Briefing:
    risk, as_of = evaluate_spot(spot, activity, doc=doc, time_slot=time_slot)
    spot_obj = spot
    return generate_briefing(spot_obj, risk, as_of, llm_fn=llm_fn)


def resolve_spot(key: str) -> Spot | None:
    return get_spot(key)
