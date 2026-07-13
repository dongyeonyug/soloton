"""파이프라인 조립 — 스냅샷 → 신선도 → 등급 → 브리핑. 라우터·테스트 공용.

C1 해소: 커밋 스냅샷 경로에서는 신선도 만료를 snapshot_as_of 기준으로 판정한다
(데모가 전부 '정보없음'으로 무너지지 않도록).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .briefing.generate import LLMFn, generate_briefing
from .engine.forecast import safest_window
from .engine.risk import evaluate, mark_stale
from .ingest.cache import SnapshotDoc, get_snapshot
from .models import Activity, Briefing, RiskGrade, SafeWindow
from .spots import Spot, get_spot

DEFAULT_TIME_SLOT = "현재"
# 예보 시계열 시각은 KST(Open-Meteo Asia/Seoul). '미래' 판정은 KST now 기준.
_KST = ZoneInfo("Asia/Seoul")


def safe_window_for(
    spot: Spot,
    activity: Activity,
    *,
    doc: SnapshotDoc | None = None,
    now: datetime | None = None,
) -> SafeWindow | None:
    """스냅샷 예보 시계열에서 '가장 안전한 시간대'를 계산. 데이터 없으면 None."""
    doc = doc or get_snapshot()
    snap = doc.spot(spot.id)
    if snap is None or not snap.forecast:
        return None
    ref = now or datetime.now(_KST).replace(tzinfo=None)
    return safest_window(snap.forecast, activity, now=ref)


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
    doc = doc or get_snapshot()
    risk, as_of = evaluate_spot(spot, activity, doc=doc, time_slot=time_slot)

    # 프리-베이크 산문은 프로덕션 기본 경로(레저·현재, 주입 LLM 없음)에서만 사용한다.
    # 비기본 활동/시간대나 테스트 주입 LLM 은 기존 라이브 경로를 그대로 탄다.
    baked_prose: str | None = None
    baked_llm_used = False
    if llm_fn is None and activity is Activity.LEISURE and time_slot == DEFAULT_TIME_SLOT:
        snap = doc.spot(spot.id)
        if snap is not None and snap.llm_prose is not None:
            baked_prose = snap.llm_prose
            baked_llm_used = snap.llm_used

    return generate_briefing(
        spot,
        risk,
        as_of,
        llm_fn=llm_fn,
        baked_prose=baked_prose,
        baked_llm_used=baked_llm_used,
        safe_window=safe_window_for(spot, activity, doc=doc),
    )


def resolve_spot(key: str) -> Spot | None:
    return get_spot(key)
