"""지점 원 관측값 + as-of."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..ingest.cache import get_snapshot

router = APIRouter(prefix="/api", tags=["observations"])


@router.get("/observations/{spot_id}")
def observations(spot_id: str):
    doc = get_snapshot()
    snap = doc.spot(spot_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"unknown spot: {spot_id}")
    return {
        "spot_id": spot_id,
        "snapshot_as_of": doc.snapshot_as_of,
        "observations": [o.model_dump() for o in snap.observations],
        "advisory": snap.advisory.model_dump(),
    }
