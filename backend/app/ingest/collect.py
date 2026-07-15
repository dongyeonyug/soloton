"""배치 수집 → 스냅샷 직렬화. GH Actions snapshot.yml 이 이걸 실행해 commit-back.

키 부재/실패 지점은 결측으로 채워 스키마를 유지(크래시 없음).
`python -m app.ingest.collect` 로도 실행 가능.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from ..clients.openmeteo import ForecastSourceUnavailableError, OpenMeteoProvider
from ..clients.resolver import get_provider
from ..config import get_settings
from ..spots import all_spots
from .advisory_history import capture_advisory_history
from .cache import SNAPSHOT_PATH, SNAPSHOT_SCHEMA_VERSION, SnapshotDoc, SpotSnapshot
from ..models import ForecastCollectionStatus, MissingReason, ProseStatus
from .normalize import normalize_spot


async def collect_all(now: datetime | None = None) -> SnapshotDoc:
    settings = get_settings()
    fetched_at = now or datetime.now(timezone.utc).replace(tzinfo=None)
    provider = get_provider(settings)
    # '가장 안전한 시간' 예보 시계열은 항상 예보모델(Open-Meteo) 소스 — 현재값 provider 와 무관.
    forecaster = OpenMeteoProvider()
    spots = all_spots()

    async def one(spot):
        observation_started = perf_counter()
        collection_failure: MissingReason | None = None
        try:
            reading = await asyncio.wait_for(
                provider.fetch_spot(spot),
                timeout=settings.collect_spot_timeout_seconds,
            )
        except TimeoutError:
            reading = None
            collection_failure = MissingReason.SOURCE_TIMEOUT
        except Exception:
            reading = None
            collection_failure = MissingReason.SOURCE_UNAVAILABLE
        observation_fetch_duration_ms = round((perf_counter() - observation_started) * 1000)
        if reading is not None and reading.observed_at is None:
            reading.observed_at = fetched_at  # provider 가 시각 미제공 시 수집시각으로
        observations, advisory = normalize_spot(
            spot,
            reading,
            fetched_at=fetched_at,
            source_labels=provider.source_labels,
            collection_failure=collection_failure,
        )
        forecast_started = perf_counter()
        forecast_status = ForecastCollectionStatus.AVAILABLE
        forecast_missing_reason: MissingReason | None = None
        try:
            forecast = await asyncio.wait_for(
                forecaster.fetch_forecast_series(spot),
                timeout=settings.collect_forecast_timeout_seconds,
            )
            if not forecast:
                forecast_status = ForecastCollectionStatus.EMPTY_RESPONSE
                forecast_missing_reason = MissingReason.SOURCE_RETURNED_NO_VALUE
        except TimeoutError:
            forecast = []
            forecast_status = ForecastCollectionStatus.SOURCE_TIMEOUT
            forecast_missing_reason = MissingReason.SOURCE_TIMEOUT
        except ForecastSourceUnavailableError:
            forecast = []
            forecast_status = ForecastCollectionStatus.SOURCE_UNAVAILABLE
            forecast_missing_reason = MissingReason.SOURCE_UNAVAILABLE
        except Exception:
            forecast = []
            forecast_status = ForecastCollectionStatus.SOURCE_UNAVAILABLE
            forecast_missing_reason = MissingReason.SOURCE_UNAVAILABLE
        forecast_fetch_duration_ms = round((perf_counter() - forecast_started) * 1000)
        return spot.id, SpotSnapshot(
            observations=observations,
            advisory=advisory,
            forecast=forecast,
            forecast_status=forecast_status,
            forecast_missing_reason=forecast_missing_reason,
            forecast_collected_at=fetched_at,
            observation_fetch_duration_ms=observation_fetch_duration_ms,
            forecast_fetch_duration_ms=forecast_fetch_duration_ms,
        )

    results = await asyncio.gather(*(one(s) for s in spots))
    return SnapshotDoc(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        snapshot_as_of=fetched_at,
        source=f"live-collect ({provider.name})",
        spots=dict(results),
    )


def write_snapshot(doc: SnapshotDoc, path: Path = SNAPSHOT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc.model_dump_json(indent=2))


DEFAULT_BATCH_LLM_TIMEOUT_SECONDS = 8.0


def _with_timeout(llm_fn, timeout_seconds: float):
    """LLM 호출 하나에만 제한 시간을 적용한다.

    배치 루프 자체는 순차다. 시간 초과된 네트워크 호출은 기다리지 않고 해당 지점을
    generation_unavailable 로 남기며 다음 지점으로 진행한다.
    """

    def call(system: str, user: str) -> str:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(llm_fn, system, user)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            raise TimeoutError(f"LLM generation exceeded {timeout_seconds}s") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    return call


def bake_briefings(
    doc: SnapshotDoc,
    *,
    llm_fn=None,
    timeout_seconds: float = DEFAULT_BATCH_LLM_TIMEOUT_SECONDS,
) -> None:
    """크론 시 기본 현재 브리핑 산문을 미리 생성해 스냅샷에 저장.

    가드를 통과한 산문만 VERIFIED 로 저장한다. 키·생성 실패·시간 초과는 각 지점에
    generation_unavailable 상태로 남긴다. 배치 외 공개 요청에서 LLM 을 호출하지 않는다.
    """
    # 지연 임포트로 import 사이클 회피(service 는 ingest.cache 만 의존).
    from ..briefing.generate import _default_llm, generate_briefing
    from ..service import DEFAULT_TIME_SLOT, evaluate_spot

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    # 실제 Anthropic 클라이언트는 HTTP 계층에도 같은 제한 시간을 건다. 주입 함수는
    # 테스트 전용이므로 배치 래퍼로만 제한한다.
    effective_llm = (
        llm_fn
        if llm_fn is not None
        else _default_llm(timeout_seconds=timeout_seconds)
    )

    for spot in all_spots():
        snap = doc.spot(spot.id)
        if snap is None:
            continue
        snap.llm_prose = None
        snap.prose_status = ProseStatus.GENERATION_UNAVAILABLE
        if effective_llm is None:
            continue
        try:
            risk, as_of = evaluate_spot(spot, doc=doc, time_slot=DEFAULT_TIME_SLOT)
            briefing = generate_briefing(
                spot,
                risk,
                as_of,
                llm_fn=(
                    _with_timeout(effective_llm, timeout_seconds)
                    if llm_fn is not None
                    else effective_llm
                ),
            )
        except Exception:
            continue  # 한 지점 실패가 전체 수집을 막지 않는다
        snap.prose_status = briefing.prose_status
        if briefing.prose_status == ProseStatus.VERIFIED:
            snap.llm_prose = briefing.llm_prose


def has_any_present(doc: SnapshotDoc) -> bool:
    """수집 결과에 실측값이 하나라도 있으면 True."""
    return any(
        not obs.is_missing
        for snap in doc.spots.values()
        for obs in snap.observations
    )


def main() -> None:
    settings = get_settings()
    doc = asyncio.run(collect_all())
    # 마지막 성공 스냅샷 보호: 전부 결측(키 없음/전량 실패)이면 seed/기존 스냅샷 유지
    if not has_any_present(doc):
        if settings.resolved_provider != "openmeteo":
            # 인증키가 설정된 라이브 수집에서 전량 결측 = 진짜 실패(파서 붕괴/API 장애).
            # 조용히 종료0 하면 크론이 죽은 채 초록불로 방치되므로 비정상 종료해
            # GH Actions 를 빨간불로 만든다. 기존 스냅샷은 덮어쓰지 않아 서빙은 무사.
            raise SystemExit(
                "collect: 인증키가 설정됐는데 실측값 0건 — 수집 실패로 판단해 "
                f"비정상 종료(기존 스냅샷은 유지). (source={doc.source})"
            )
        print(
            "collect: 실측값 0건 — 기존 스냅샷 유지(덮어쓰기 안 함). "
            f"(source={doc.source}) 인증키 설정 여부를 확인하세요."
        )
        return
    # AI 켜져 있으면 기본 현재 브리핑 산문을 미리 구워 스냅샷에 담는다.
    try:
        history_result = asyncio.run(
            capture_advisory_history(
                getattr(settings, "kma_api_key", ""),
                now=doc.snapshot_as_of,
            )
        )
    except Exception:
        history_result = None
    bake_briefings(doc, timeout_seconds=settings.batch_llm_timeout_seconds)
    baked = sum(
        1 for s in doc.spots.values()
        if s.prose_status == ProseStatus.VERIFIED
    )
    observation_times = [
        snap.observation_fetch_duration_ms
        for snap in doc.spots.values()
        if snap.observation_fetch_duration_ms is not None
    ]
    timing_note = ""
    if observation_times:
        timing_note = (
            f", observation_fetch_ms=min:{min(observation_times)} "
            f"max:{max(observation_times)}"
        )
    write_snapshot(doc)
    history_note = ""
    if history_result is not None:
        history_note = (
            ", advisory_history="
            f"records:{history_result.warning_record_count} "
            f"scope_captures:{history_result.scope_capture_count} "
            f"changed:{history_result.changed}"
        )
    print(
        f"snapshot written: {SNAPSHOT_PATH} (as_of={doc.snapshot_as_of}, "
        f"source={doc.source}, baked_briefings={baked}/{len(doc.spots)}"
        f"{timing_note}{history_note})"
    )


if __name__ == "__main__":
    main()
