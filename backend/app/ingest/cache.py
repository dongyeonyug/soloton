"""스냅샷 읽기 계층. 커밋된 snapshot.json 이 데모의 사실 원천(AC9).

라이브 API 다운·키 부재와 무관하게 as-of 타임스탬프를 동반한 관측을 서빙한다.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ..config import DATA_DIR
from ..models import Advisory, ForecastPoint, MarineObservation, Metric

SNAPSHOT_PATH = DATA_DIR / "snapshot.json"


class SpotSnapshot(BaseModel):
    observations: list[MarineObservation] = Field(default_factory=list)
    advisory: Advisory

    # 크론 프리-베이크(기본 활동=레저) 산문. 크론 시 가드를 통과한 LLM 산문만 채워지고,
    # 없으면(키 부재/가드 실패) None → 서빙 시 라이브 경로로 폴백. 서빙 단계에서도
    # 런타임 가드를 재통과시키므로 저장분도 '숫자 0개'가 최종 보장된다(이중 게이트).
    llm_prose: str | None = None
    llm_used: bool = False

    # E2: '가장 안전한 시간' 산정용 시간별 예보 시계열(Open-Meteo). 비어있으면 안전창 미표시.
    forecast: list[ForecastPoint] = Field(default_factory=list)

    def as_map(self) -> dict[Metric, MarineObservation]:
        return {obs.metric: obs for obs in self.observations}


class SnapshotDoc(BaseModel):
    snapshot_as_of: datetime
    source: str = "seed"
    spots: dict[str, SpotSnapshot] = Field(default_factory=dict)

    def spot(self, spot_id: str) -> SpotSnapshot | None:
        return self.spots.get(spot_id)


def load_snapshot(path: Path = SNAPSHOT_PATH) -> SnapshotDoc:
    with open(path, encoding="utf-8") as f:
        return SnapshotDoc.model_validate(json.load(f))


# 프로세스 캐시 (파일 mtime 로 무효화)
_cache: tuple[float, SnapshotDoc] | None = None


def get_snapshot(path: Path = SNAPSHOT_PATH) -> SnapshotDoc:
    global _cache
    mtime = path.stat().st_mtime
    if _cache is None or _cache[0] != mtime:
        _cache = (mtime, load_snapshot(path))
    return _cache[1]
