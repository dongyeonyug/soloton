"""배치 수집 → 스냅샷 직렬화. GH Actions snapshot.yml 이 이걸 실행해 commit-back.

키 부재/실패 지점은 결측으로 채워 스키마를 유지(크래시 없음).
`python -m app.ingest.collect` 로도 실행 가능.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from ..clients.openmeteo import OpenMeteoProvider
from ..clients.resolver import get_provider
from ..config import get_settings
from ..spots import all_spots
from .cache import SNAPSHOT_PATH, SnapshotDoc, SpotSnapshot
from .normalize import normalize_spot


async def collect_all(now: datetime | None = None) -> SnapshotDoc:
    settings = get_settings()
    fetched_at = now or datetime.now(timezone.utc).replace(tzinfo=None)
    provider = get_provider(settings)
    # '가장 안전한 시간' 예보 시계열은 항상 예보모델(Open-Meteo) 소스 — 현재값 provider 와 무관.
    forecaster = OpenMeteoProvider()
    spots = all_spots()

    async def one(spot):
        reading = await provider.fetch_spot(spot)
        if reading is not None and reading.observed_at is None:
            reading.observed_at = fetched_at  # provider 가 시각 미제공 시 수집시각으로
        observations, advisory = normalize_spot(
            spot, reading, fetched_at=fetched_at, source_labels=provider.source_labels
        )
        forecast = await forecaster.fetch_forecast_series(spot)
        return spot.id, SpotSnapshot(
            observations=observations, advisory=advisory, forecast=forecast
        )

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


def bake_briefings(doc: SnapshotDoc, *, llm_fn=None) -> None:
    """크론 시 기본 활동(레저·현재) 산문을 미리 생성해 스냅샷에 저장.

    가드를 통과한 LLM 산문만 저장한다(llm_used=True). 키가 없으면(테스트 주입 llm_fn
    도 없으면) 아무것도 하지 않는다 → 서빙 시 라이브 경로 폴백. 서빙 단계에서 저장 산문을
    가드에 다시 통과시키므로 '숫자 0개'는 이중으로 보장된다.
    """
    # 지연 임포트로 import 사이클 회피(service 는 ingest.cache 만 의존).
    from ..briefing.generate import generate_briefing
    from ..models import Activity
    from ..service import DEFAULT_TIME_SLOT, evaluate_spot

    settings = get_settings()
    if llm_fn is None and not settings.has_llm:
        return

    for spot in all_spots():
        snap = doc.spot(spot.id)
        if snap is None:
            continue
        try:
            risk, as_of = evaluate_spot(
                spot, Activity.LEISURE, doc=doc, time_slot=DEFAULT_TIME_SLOT
            )
            briefing = generate_briefing(spot, risk, as_of, llm_fn=llm_fn)
        except Exception:
            continue  # 한 지점 실패가 전체 수집을 막지 않는다
        if briefing.llm_used:
            snap.llm_prose = briefing.llm_prose
            snap.llm_used = True


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
    # AI 켜져 있으면 기본 활동 산문을 미리 구워 스냅샷에 담는다(서빙 시 라이브 호출 제거).
    bake_briefings(doc)
    baked = sum(1 for s in doc.spots.values() if s.llm_used)
    write_snapshot(doc)
    print(
        f"snapshot written: {SNAPSHOT_PATH} (as_of={doc.snapshot_as_of}, "
        f"source={doc.source}, baked_briefings={baked}/{len(doc.spots)})"
    )


if __name__ == "__main__":
    main()
