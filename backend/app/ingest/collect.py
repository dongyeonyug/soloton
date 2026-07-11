"""배치 수집 → 스냅샷 직렬화. GH Actions snapshot.yml 이 이걸 실행해 commit-back.

키 부재/실패 지점은 결측으로 채워 스키마를 유지(크래시 없음).
`python -m app.ingest.collect` 로도 실행 가능.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from ..clients.resolver import get_provider
from ..config import get_settings
from ..spots import all_spots
from .cache import SNAPSHOT_PATH, SnapshotDoc, SpotSnapshot
from .normalize import normalize_spot


async def collect_all(now: datetime | None = None) -> SnapshotDoc:
    settings = get_settings()
    fetched_at = now or datetime.now(timezone.utc).replace(tzinfo=None)
    provider = get_provider(settings)
    spots = all_spots()

    async def one(spot):
        reading = await provider.fetch_spot(spot)
        if reading is not None and reading.observed_at is None:
            reading.observed_at = fetched_at  # provider 가 시각 미제공 시 수집시각으로
        observations, advisory = normalize_spot(
            spot, reading, fetched_at=fetched_at, source_labels=provider.source_labels
        )
        return spot.id, SpotSnapshot(observations=observations, advisory=advisory)

    results = await asyncio.gather(*(one(s) for s in spots))
    return SnapshotDoc(
        snapshot_as_of=fetched_at,
        source=f"live-collect ({provider.name})",
        spots=dict(results),
    )


def write_snapshot(doc: SnapshotDoc, path: Path = SNAPSHOT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc.model_dump_json(indent=2))


def has_any_present(doc: SnapshotDoc) -> bool:
    """수집 결과에 실측값이 하나라도 있으면 True."""
    return any(
        not obs.is_missing
        for snap in doc.spots.values()
        for obs in snap.observations
    )


def main() -> None:
    doc = asyncio.run(collect_all())
    # 마지막 성공 스냅샷 보호: 전부 결측(키 없음/전량 실패)이면 seed/기존 스냅샷 유지
    if not has_any_present(doc):
        print(
            "collect: 실측값 0건 — 기존 스냅샷 유지(덮어쓰기 안 함). "
            f"(source={doc.source}) 인증키 설정 여부를 확인하세요."
        )
        return
    write_snapshot(doc)
    print(f"snapshot written: {SNAPSHOT_PATH} (as_of={doc.snapshot_as_of}, source={doc.source})")


if __name__ == "__main__":
    main()
