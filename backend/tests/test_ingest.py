"""AC1: 수집·정규화 스키마·결측 플래그·per-metric 타임스탬프 검증."""

from datetime import datetime

from app.clients.base import ProviderReading
from app.ingest.cache import get_snapshot
from app.ingest.normalize import ALL_METRICS, normalize_spot
from app.models import Metric
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
