"""Phase 1 물놀이 계획 API.

이 라우터는 계획 입력을 해석하지 않는다. 선택 UI가 실제 예보 시각만 보이게 하고,
결정형 서비스가 만든 결과를 그대로 반환한다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import PlanBriefing, PlanIntent, PlanOptions
from ..service import build_plan_briefing, plan_options_for, resolve_spot

router = APIRouter(prefix="/api", tags=["plans"])


def _spot(spot_id: str):
    spot = resolve_spot(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail=f"unknown spot: {spot_id}")
    return spot


@router.get("/plans/options/{spot_id}", response_model=PlanOptions)
def plan_options(spot_id: str) -> PlanOptions:
    """선택 가능한 실제 미래 예보 시각을 반환한다."""
    return plan_options_for(_spot(spot_id))


@router.post("/plans/briefing", response_model=PlanBriefing)
def plan_briefing(intent: PlanIntent) -> PlanBriefing:
    """선택형 계획을 결정형 물놀이 브리핑으로 변환한다."""
    return build_plan_briefing(_spot(intent.spot_id), intent)
