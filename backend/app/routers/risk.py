"""지점 위험도 등급 (활동별)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import Activity
from ..service import evaluate_spot, resolve_spot

router = APIRouter(prefix="/api", tags=["risk"])


@router.get("/risk/{spot_id}")
def risk(spot_id: str, activity: Activity = Activity.LEISURE):
    spot = resolve_spot(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail=f"unknown spot: {spot_id}")
    grade, as_of = evaluate_spot(spot, activity)
    return {"snapshot_as_of": as_of, **grade.model_dump()}
