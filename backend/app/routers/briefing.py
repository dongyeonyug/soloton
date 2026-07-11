"""지점 브리핑 (슬롯필 + 가드된 LLM 산문)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import Activity
from ..service import brief_spot, resolve_spot

router = APIRouter(prefix="/api", tags=["briefing"])


@router.get("/briefing/{spot_id}")
def briefing(spot_id: str, activity: Activity = Activity.LEISURE):
    spot = resolve_spot(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail=f"unknown spot: {spot_id}")
    result = brief_spot(spot, activity)
    return result.model_dump()
