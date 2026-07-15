"""AC1: 수집·정규화 스키마·결측 플래그·per-metric 타임스탬프 검증."""

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.clients.base import ProviderReading
from app.ingest import advisory_history
from app.ingest import collect
from app.ingest.cache import SnapshotDoc, SpotSnapshot, get_snapshot
from app.ingest.normalize import ALL_METRICS, normalize_spot
from app.models import ForecastCollectionStatus, Metric, MissingReason
from app.spots import all_spots, get_spot


def test_snapshot_covers_all_spots():
    doc = get_snapshot()
    spot_ids = {s.id for s in all_spots()}
    assert set(doc.spots.keys()) == spot_ids
    assert 10 <= len(spot_ids) <= 15


def test_every_spot_has_full_metric_schema():
    doc = get_snapshot()
    for spot_id, snap in doc.spots.items():
        metrics = {obs.metric for obs in snap.observations}
        assert set(ALL_METRICS).issubset(metrics), f"{spot_id} missing metrics"


def test_missing_flag_and_timestamp_consistency():
    """결측이면 value None + observed_at None; present 면 둘 다 세팅(AC1)."""
    doc = get_snapshot()
    for snap in doc.spots.values():
        for obs in snap.observations:
            if obs.is_missing:
                assert obs.value is None
                assert obs.observed_at is None
            else:
                assert obs.value is not None
                assert obs.observed_at is not None


def test_normalize_missing_critical_metric_present():
    """임계지표가 provider 결과에 없으면 결측으로 정규화된다."""
    observations, _ = normalize_spot(
        get_spot("cheongsapo"),
        reading=ProviderReading(metrics={Metric.WAVE_HEIGHT: 0.4}),
        fetched_at=datetime(2026, 7, 10),
    )
    wind = next(o for o in observations if o.metric is Metric.WIND_SPEED)
    assert wind.is_missing is True
    assert wind.value is None
    assert wind.observed_at is None


def test_normalize_absent_becomes_missing():
    """클라이언트 None → 전 지표 결측(크래시 없음)."""
    spot = get_spot("haeundae")
    observations, advisory = normalize_spot(
        spot, reading=None, fetched_at=datetime(2026, 7, 10)
    )
    assert len(observations) == len(ALL_METRICS)
    assert all(o.is_missing for o in observations)
    assert advisory.is_missing is True


def test_normalize_preserves_collection_timeout_reason():
    observations, _ = normalize_spot(
        get_spot("haeundae"),
        reading=None,
        fetched_at=datetime(2026, 7, 10),
        collection_failure=MissingReason.SOURCE_TIMEOUT,
    )
    assert all(obs.missing_reason is MissingReason.SOURCE_TIMEOUT for obs in observations)


def _all_missing_doc(source: str) -> SnapshotDoc:
    spot = get_spot("haeundae")
    observations, advisory = normalize_spot(
        spot, reading=None, fetched_at=datetime(2026, 7, 10)
    )
    return SnapshotDoc(
        snapshot_as_of=datetime(2026, 7, 10),
        source=source,
        spots={spot.id: SpotSnapshot(observations=observations, advisory=advisory)},
    )


def _patch_collect(monkeypatch, *, provider: str, doc: SnapshotDoc) -> None:
    async def fake_collect_all(now=None):
        return doc

    monkeypatch.setattr(collect, "collect_all", fake_collect_all)
    monkeypatch.setattr(
        collect, "get_settings", lambda: SimpleNamespace(resolved_provider=provider)
    )


def test_all_missing_with_live_keys_exits_nonzero(monkeypatch):
    """T5: 인증키 설정된 수집에서 전량 결측 = 진짜 실패 → 비정상 종료(크론 빨간불)."""
    _patch_collect(monkeypatch, provider="hybrid", doc=_all_missing_doc("live-collect (hybrid)"))
    with pytest.raises(SystemExit):
        collect.main()


def test_all_missing_keyless_keeps_snapshot_and_exit_zero(monkeypatch, capsys):
    """키 없는(openmeteo) 전량 결측은 기존 동작 유지: 스냅샷 보존 + 정상 종료."""
    _patch_collect(
        monkeypatch, provider="openmeteo", doc=_all_missing_doc("live-collect (openmeteo)")
    )
    written: list[SnapshotDoc] = []
    monkeypatch.setattr(collect, "write_snapshot", lambda doc, path=None: written.append(doc))
    collect.main()  # SystemExit 없이 통과해야 한다
    assert written == []  # 기존 스냅샷 덮어쓰기 없음
    assert "기존 스냅샷 유지" in capsys.readouterr().out


def test_successful_collect_captures_advisory_history(monkeypatch):
    spot = get_spot("haeundae")
    observations, advisory = normalize_spot(
        spot,
        reading=ProviderReading(metrics={Metric.WAVE_HEIGHT: 0.4}),
        fetched_at=datetime(2026, 7, 10),
    )
    doc = SnapshotDoc(
        snapshot_as_of=datetime(2026, 7, 10),
        source="test",
        spots={spot.id: SpotSnapshot(observations=observations, advisory=advisory)},
    )

    async def fake_collect_all(now=None):
        return doc

    captured = []

    async def fake_capture(api_key, *, now):
        captured.append((api_key, now))
        return advisory_history.AdvisoryHistoryCapture(3, 1, True)

    settings = SimpleNamespace(
        resolved_provider="openmeteo",
        kma_api_key="history-key",
        batch_llm_timeout_seconds=1.0,
    )
    monkeypatch.setattr(collect, "collect_all", fake_collect_all)
    monkeypatch.setattr(collect, "get_settings", lambda: settings)
    monkeypatch.setattr(collect, "capture_advisory_history", fake_capture)
    monkeypatch.setattr(collect, "bake_briefings", lambda *args, **kwargs: None)
    monkeypatch.setattr(collect, "write_snapshot", lambda *args, **kwargs: None)

    collect.main()

    assert captured == [("history-key", doc.snapshot_as_of)]


def test_collect_records_timeout_and_per_spot_durations(monkeypatch):
    """T4: 느린 소스는 수집 배치를 막지 않고 원인·소요 시간을 스냅샷에 남긴다."""
    spot = get_spot("haeundae")

    class SlowProvider:
        name = "slow"
        source_labels = {}

        async def fetch_spot(self, _spot):
            await asyncio.sleep(0.02)
            return None

    class FastForecaster:
        async def fetch_forecast_series(self, _spot):
            return []

    monkeypatch.setattr(
        collect,
        "get_settings",
        lambda: SimpleNamespace(
            collect_spot_timeout_seconds=0.001,
            collect_forecast_timeout_seconds=0.1,
        ),
    )
    monkeypatch.setattr(collect, "get_provider", lambda _settings: SlowProvider())
    monkeypatch.setattr(collect, "OpenMeteoProvider", lambda: FastForecaster())
    monkeypatch.setattr(collect, "all_spots", lambda: [spot])

    doc = asyncio.run(collect.collect_all(now=datetime(2026, 7, 10)))
    snap = doc.spot(spot.id)
    assert snap.observation_fetch_duration_ms is not None
    assert snap.forecast_fetch_duration_ms is not None
    assert snap.forecast_status is ForecastCollectionStatus.EMPTY_RESPONSE
    assert snap.forecast_missing_reason is MissingReason.SOURCE_RETURNED_NO_VALUE
    assert snap.forecast_collected_at == datetime(2026, 7, 10)
    assert all(
        obs.missing_reason is MissingReason.SOURCE_TIMEOUT
        for obs in snap.observations
    )
