"""E1 — 가드 시연 (준비된 시나리오 + 직접 입력).

두 엔드포인트 모두 판정을 프로덕션 브리핑 경로(`brief_spot` → 가드)에 위임한다.
여기서 새로 판단하는 것은 없다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..briefing.demo import GuardDemo, GuardVerdict, check_prose, run_demo
from ..service import resolve_spot

router = APIRouter(prefix="/api", tags=["guard"])

DEFAULT_DEMO_SPOT = "haeundae"
# 시연용 입력 상한. 브리핑 산문 한 단락이면 충분하다.
MAX_TEXT_LEN = 300


def _spot(spot_id: str):
    spot = resolve_spot(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail=f"unknown spot: {spot_id}")
    return spot


@router.get("/guard/demo", response_model=GuardDemo)
def guard_demo(spot_id: str = DEFAULT_DEMO_SPOT):
    """재현한 환각 문장들을 실제 가드에 태운 결과."""
    return run_demo(_spot(spot_id))


@router.get("/guard/check", response_model=GuardVerdict)
def guard_check(
    text: str = Query(..., min_length=1, max_length=MAX_TEXT_LEN),
    spot_id: str = DEFAULT_DEMO_SPOT,
):
    """사용자가 직접 쓴 문장을 같은 가드에 태운다(심사위원 직접 시험용)."""
    stripped = text.strip()
    if not stripped:
        raise HTTPException(status_code=422, detail="empty text")
    return check_prose(_spot(spot_id), stripped)
