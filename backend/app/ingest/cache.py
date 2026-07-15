"""스냅샷 읽기 계층. 커밋된 snapshot.json 이 데모의 사실 원천(AC9).

라이브 API 다운·키 부재와 무관하게 as-of 타임스탬프를 동반한 관측을 서빙한다.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ..config import DATA_DIR
from ..models import (
    Advisory,
    ForecastCollectionStatus,
    ForecastPoint,
    MissingReason,
    MarineObservation,
    Metric,
    ProseStatus,
)

SNAPSHOT_PATH = DATA_DIR / "snapshot.json"
SNAPSHOT_SCHEMA_VERSION = 2


class SpotSnapshot(BaseModel):
    observations: list[MarineObservation] = Field(default_factory=list)
    advisory: Advisory

    # 크론 프리-베이크 산문. VERIFIED 일 때만 llm_prose 를 저장한다. 공개 서빙도 저장분을
    # 다시 가드에 통과시키며, 상태는 생성 실패와 가드 차단을 숨기지 않는다.
    llm_prose: str | None = None
    prose_status: ProseStatus = ProseStatus.GENERATION_UNAVAILABLE

    # 수집 배치 진단용. 공개 브리핑은 이 값을 기다리지 않고 저장된 스냅샷만 읽는다.
    observation_fetch_duration_ms: int | None = None
    forecast_fetch_duration_ms: int | None = None

    # T6: 시간별 예보의 수집 결과도 보존한다. 구 스냅샷은 LEGACY_UNKNOWN 으로 읽는다.
    forecast: list[ForecastPoint] = Field(default_factory=list)
    forecast_status: ForecastCollectionStatus = ForecastCollectionStatus.LEGACY_UNKNOWN
    forecast_missing_reason: MissingReason | None = None
    forecast_collected_at: datetime | None = None

    def as_map(self) -> dict[Metric, MarineObservation]:
        return {obs.metric: obs for obs in self.observations}


class SnapshotDoc(BaseModel):
    # 누락된 값은 구 스냅샷(v1)으로 읽는다. 구 버전의 산문은 공개 경로에서 재사용하지 않는다.
    schema_version: int = 1
    snapshot_as_of: datetime
    source: str = "seed"
    spots: dict[str, SpotSnapshot] = Field(default_factory=dict)

    def spot(self, spot_id: str) -> SpotSnapshot | None:
        return self.spots.get(spot_id)

    @property
    def has_current_prose_contract(self) -> bool:
        return self.schema_version == SNAPSHOT_SCHEMA_VERSION


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
