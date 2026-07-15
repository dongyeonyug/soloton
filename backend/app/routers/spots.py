"""지점 목록 + 개요(등급 포함) — 지도/리스트 뷰용."""

from __future__ import annotations

from fastapi import APIRouter

from ..ingest.cache import get_snapshot
from ..service import evaluate_spot
from ..spots import all_spots

router = APIRouter(prefix="/api", tags=["spots"])


@router.get("/spots")
def list_spots():
    return [s.model_dump() for s in all_spots()]


@router.get("/overview")
def overview():
    """전 지점의 해안 활동 참고 등급 — 지도 신호등 색칠용."""
    doc = get_snapshot()
    out = []
    for spot in all_spots():
        risk, as_of = evaluate_spot(spot, doc=doc)
        out.append(
            {
                "id": spot.id,
                "name": spot.name,
                "lat": spot.lat,
                "lng": spot.lng,
                "type": spot.type.value,
                "grade": risk.grade.value,
                "grade_ko": risk.grade.label_ko,
                "has_missing_critical": risk.has_missing_critical,
            }
        )
    return {"snapshot_as_of": doc.snapshot_as_of, "spots": out}
