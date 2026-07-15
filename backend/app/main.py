"""FastAPI 앱 진입점."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .ingest.cache import get_snapshot
from .routers import briefing, guard, observations, risk, spots

app = FastAPI(
    title="오늘의 바다 API",
    description="환각 없는 AI 연안 해양안전 브리핑. 코드가 사실의 원천, LLM은 표현만.",
    version="0.1.0",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(spots.router)
app.include_router(observations.router)
app.include_router(risk.router)
app.include_router(briefing.router)
app.include_router(guard.router)


@app.get("/api/health")
def health():
    doc = get_snapshot()
    return {
        "status": "ok",
        "snapshot_as_of": doc.snapshot_as_of,
        "snapshot_source": doc.source,
        "spot_count": len(doc.spots),
        "llm_enabled": settings.has_llm,
        "live_keys": settings.has_live_keys,
        "snapshot_only": settings.use_snapshot_only,
    }


@app.get("/")
def root():
    return {"service": "오늘의 바다", "docs": "/docs", "disclaimer": "참고용 — 실제 해안 활동 판단 근거 아님"}
